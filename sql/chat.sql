-- Chat thread for the dashboard (your questions and Ping's answers) and the
-- "read up to here" marker. Run once in Supabase > SQL Editor. Safe to re-run.
-- (Already included in schema.sql for new setups.)

create table if not exists chat_messages (
  id bigint generated always as identity primary key,
  role text not null check (role in ('me', 'ping')),
  text text not null,
  created_at timestamptz default now(),
  is_sample boolean default false
);
alter table chat_messages enable row level security;

alter table profile add column if not exists chat_read_at timestamptz;

drop policy if exists owner_chat_read on chat_messages;
create policy owner_chat_read on chat_messages for select to authenticated using (is_ping_owner());
drop policy if exists owner_chat_write on chat_messages;
create policy owner_chat_write on chat_messages for insert to authenticated with check (is_ping_owner());

grant select, insert on chat_messages to authenticated;
grant select, insert, update, delete on chat_messages to service_role;
grant update (chat_read_at) on profile to authenticated;

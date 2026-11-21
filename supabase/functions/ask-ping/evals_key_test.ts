import { evalsProof } from "./evals_key.ts";

Deno.test("the evals proof is the same HMAC the Python runner sends (ping/evals_key.py)", async () => {
  // python -c "import hmac,hashlib;print(hmac.new(b'test-evals-key',b'ping-evals',hashlib.sha256).hexdigest())"
  const want = "72fa44938fecbcc05c30613f630e95836283df39e9f0b620179d0c72bed6d706";
  const got = await evalsProof("test-evals-key");
  if (got !== want) throw new Error(`${got} != ${want}`);
});

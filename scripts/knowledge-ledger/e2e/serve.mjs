// 組んだページを配信するだけの静的サーバ。claude.ai の iframe と同じく UTF-8 として返す
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";

const [port, file] = process.argv.slice(2);
createServer(async (req, res) => {
  if (req.url !== "/index.html") { res.writeHead(404).end(); return; }
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" }).end(await readFile(file));
}).listen(Number(port), "127.0.0.1");

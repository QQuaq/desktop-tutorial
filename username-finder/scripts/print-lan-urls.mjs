import os from "node:os";

const port = process.env.PORT || "3457";

const urls = [];
for (const ifaces of Object.values(os.networkInterfaces())) {
  for (const iface of ifaces ?? []) {
    if (iface.family !== "IPv4" || iface.internal) continue;
    urls.push(`http://${iface.address}:${port}`);
  }
}

console.log("");
console.log("=== Kullanıcı adı arama sunucusu ===");
console.log(`Bu PC:     http://127.0.0.1:${port}`);
if (urls.length) {
  console.log("Aynı Wi‑Fi / LAN:");
  for (const u of urls) console.log(`           ${u}`);
} else {
  console.log("Aynı Wi‑Fi / LAN: (IPv4 adresi bulunamadı)");
}
console.log("");
console.log("Durdurmak: pencerede Ctrl+C");
console.log("");
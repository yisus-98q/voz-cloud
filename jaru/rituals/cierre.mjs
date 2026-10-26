// Ritual de la noche - "Cierre"
// Ejecutado por la tarea programada JaruCierre (21:00)
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pendientesPath = path.join(__dirname, 'datos', 'pendientes.txt');
const logDir = path.join(__dirname, 'logs');
fs.mkdirSync(logDir, { recursive: true });

const ahora = new Date();
const fechaLarga = ahora.toLocaleDateString('es-MX', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
});
const hora = ahora.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });

let pendientes = 0;
try {
  pendientes = fs
    .readFileSync(pendientesPath, 'utf8')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#')).length;
} catch {
  pendientes = 0;
}

const lineas = [];
lineas.push('==================================================');
lineas.push(`  CIERRE DEL DIA  -  ${fechaLarga}`);
lineas.push(`  Hora: ${hora}`);
lineas.push('==================================================');
lineas.push('');
lineas.push(`  Pendientes para manana: ${pendientes}`);
lineas.push('');
lineas.push('  Descansa. El trabajo de hoy ya quedo.');
lineas.push('==================================================');

const salida = lineas.join('\n');
console.log(salida);

const logFile = path.join(logDir, `cierre-${ahora.toISOString().slice(0, 10)}.log`);
fs.appendFileSync(logFile, `[${ahora.toISOString()}] Cierre\n${salida}\n\n`, 'utf8');

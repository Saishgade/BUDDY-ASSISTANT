const DEFAULT_HOST = '127.0.0.1';
const DEFAULT_PORT = 8765;

export function buildHost(host = DEFAULT_HOST) {
  return host && host.trim() ? host.trim() : DEFAULT_HOST;
}

export async function pairWithBuddy(code, host = DEFAULT_HOST, port = DEFAULT_PORT) {
  const response = await fetch(`http://${buildHost(host)}:${port}/pair?code=${encodeURIComponent(code)}`);
  const data = await response.json();
  return data;
}

export async function sendBuddyCommand(action, payload = {}, host = DEFAULT_HOST, port = DEFAULT_PORT) {
  const response = await fetch(`http://${buildHost(host)}:${port}/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, ...payload }),
  });
  const data = await response.json();
  return data;
}

export function buildPairingUrl(code, host = DEFAULT_HOST, port = DEFAULT_PORT) {
  return `http://${buildHost(host)}:${port}/pair?code=${encodeURIComponent(code)}`;
}

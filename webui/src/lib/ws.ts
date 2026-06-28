export interface WsHandlers {
  onMessage: (data: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export interface WsClient {
  send: (data: string) => void;
  close: () => void;
}

export function createWsClient(
  path: string,
  token: string,
  handlers: WsHandlers,
): WsClient {
  let stopped = false;
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (stopped) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const sep = path.includes("?") ? "&" : "?";
    const url = `${proto}//${location.host}${path}${sep}token=${encodeURIComponent(token)}`;
    ws = new WebSocket(url);
    ws.onopen = () => handlers.onOpen?.();
    ws.onmessage = (ev) => handlers.onMessage(ev.data as string);
    ws.onclose = () => {
      ws = null;
      handlers.onClose?.();
      if (!stopped) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    };
    ws.onerror = () => {
      ws?.close();
    };
  }

  connect();

  return {
    send: (data: string) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
    },
    close: () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
      ws = null;
    },
  };
}

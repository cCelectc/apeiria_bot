export function createSseClient(
  url: string,
  token: string,
  onMessage: (data: string) => void,
  onError?: (err: Error) => void,
): { close: () => void } {
  const controller = new AbortController();
  let stopped = false;

  async function connect() {
    while (!stopped) {
      try {
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE connection failed: ${response.status}`);
        }

        const reader = response.body
          .pipeThrough(new TextDecoderStream())
          .getReader();

        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += value;
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              onMessage(line.slice(6));
            }
          }
        }
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError" || stopped) break;
        onError?.(err as Error);
      }

      if (!stopped) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
    }
  }

  connect();

  return {
    close: () => {
      stopped = true;
      controller.abort();
    },
  };
}

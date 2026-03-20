export class BridgeError extends Error {
  constructor(message, payload = null) {
    super(message);
    this.name = 'BridgeError';
    this.payload = payload;
  }
}

class BridgeSocket extends EventTarget {
  constructor(url) {
    super();
    this.url = url;
    this.socket = new WebSocket(url);
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener('open', () => resolve(this), { once: true });
      this.socket.addEventListener('error', (event) => reject(event), { once: true });
    });

    this.socket.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(event.data);
        const eventName = payload.event || payload.type || 'message';
        this.dispatchEvent(new CustomEvent(eventName, { detail: payload }));
        this.dispatchEvent(new CustomEvent('message', { detail: payload }));
      } catch (error) {
        this.dispatchEvent(new CustomEvent('parse_error', { detail: error }));
      }
    });

    this.socket.addEventListener('close', (event) => {
      this.dispatchEvent(new CustomEvent('close', { detail: event }));
    });

    this.socket.addEventListener('error', (event) => {
      this.dispatchEvent(new CustomEvent('error', { detail: event }));
    });
  }

  send(payload) {
    this.socket.send(JSON.stringify(payload));
  }

  close() {
    this.socket.close();
  }

  on(eventName, handler) {
    this.addEventListener(eventName, (event) => handler(event.detail));
    return this;
  }
}

export class SubscriptionSocket extends BridgeSocket {
  async subscribe(payload) {
    await this.ready;
    this.send({ type: 'subscribe', ...payload });
    return this;
  }

  async unsubscribe() {
    await this.ready;
    this.send({ type: 'unsubscribe' });
  }

  async ping() {
    await this.ready;
    this.send({ type: 'ping' });
  }
}

export class RequestEventsSocket extends BridgeSocket {}

export class BrowserClient {
  constructor(options = {}) {
    const baseUrl = options.baseUrl || 'http://127.0.0.1:7878';
    const normalized = new URL(baseUrl);
    this.baseUrl = normalized.toString().replace(/\/$/, '');
    this.wsBaseUrl = (options.wsBaseUrl || this.baseUrl)
      .replace(/^http:/, 'ws:')
      .replace(/^https:/, 'wss:')
      .replace(/\/$/, '');
  }

  async request(payload) {
    const response = await fetch(`${this.baseUrl}/requests`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new BridgeError(data.error || `request submission failed with ${response.status}`, data);
    }
    return data;
  }

  async getRequest(requestId) {
    const response = await fetch(`${this.baseUrl}/requests/${encodeURIComponent(requestId)}`);
    const data = await response.json();
    if (!response.ok) {
      throw new BridgeError(data.error || `request lookup failed with ${response.status}`, data);
    }
    return data;
  }

  async getRequestResult(requestId) {
    const response = await fetch(`${this.baseUrl}/requests/${encodeURIComponent(requestId)}/result`);
    const data = await response.json();
    if (!response.ok) {
      throw new BridgeError(data.error || `request result failed with ${response.status}`, data);
    }
    return data;
  }

  async waitForResult(requestId, { pollMs = 250 } = {}) {
    for (;;) {
      const status = await this.getRequestResult(requestId);
      if (status.state === 'done') return status.result;
      if (status.state === 'failed') {
        throw new BridgeError(status.error || 'request failed', status);
      }
      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }
  }

  openSubscriptionSocket() {
    return new SubscriptionSocket(`${this.wsBaseUrl}/ws/subscriptions`);
  }

  openRequestEventsSocket() {
    return new RequestEventsSocket(`${this.wsBaseUrl}/ws/requests`);
  }

  async health() {
    const response = await fetch(`${this.baseUrl}/health`);
    const data = await response.json();
    if (!response.ok) {
      throw new BridgeError(data.error || `health failed with ${response.status}`, data);
    }
    return data;
  }
}

export function createClient(options) {
  return new BrowserClient(options);
}

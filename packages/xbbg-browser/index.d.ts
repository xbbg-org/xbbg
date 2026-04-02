export interface StringPair {
  key: string;
  value: string;
}

export interface RequestPayload {
  requestId?: string;
  service: string;
  operation: string;
  requestOperation?: string;
  extractor?: string;
  securities?: string[];
  security?: string;
  fields?: string[];
  overrides?: StringPair[];
  elements?: StringPair[];
  kwargs?: StringPair[];
  startDate?: string;
  endDate?: string;
  startDatetime?: string;
  endDatetime?: string;
  eventType?: string;
  eventTypes?: string[];
  interval?: number;
  options?: StringPair[];
  fieldTypes?: StringPair[];
  includeSecurityErrors?: boolean;
  validateFields?: boolean;
  searchSpec?: string;
  fieldIds?: string[];
  format?: string;
}

export interface RequestAccepted {
  requestId: string;
  state: 'queued';
}

export interface RequestRecord {
  requestId: string;
  state: 'queued' | 'running' | 'done' | 'failed';
  submittedAt: string;
  startedAt?: string;
  completedAt?: string;
  result?: unknown;
  error?: string;
}

export interface SubscriptionCommand {
  subscriptionId?: string;
  service?: string;
  topics: string[];
  fields: string[];
  options?: string[];
  streamCapacity?: number;
  flushThreshold?: number;
  overflowPolicy?: string;
}

export class BridgeError extends Error {
  payload: unknown;
}

export class SubscriptionSocket extends EventTarget {
  constructor(url: string);
  readonly url: string;
  readonly ready: Promise<this>;
  subscribe(payload: SubscriptionCommand): Promise<this>;
  unsubscribe(): Promise<void>;
  ping(): Promise<void>;
  close(): void;
  on(eventName: string, handler: (payload: any) => void): this;
}

export class RequestEventsSocket extends EventTarget {
  constructor(url: string);
  readonly url: string;
  readonly ready: Promise<this>;
  close(): void;
  on(eventName: string, handler: (payload: any) => void): this;
}

export interface BrowserClientOptions {
  baseUrl?: string;
  wsBaseUrl?: string;
}

export class BrowserClient {
  constructor(options?: BrowserClientOptions);
  request(payload: RequestPayload): Promise<RequestAccepted>;
  getRequest(requestId: string): Promise<RequestRecord>;
  getRequestResult(requestId: string): Promise<{ requestId: string; state: string; result?: unknown; error?: string }>;
  waitForResult(requestId: string, options?: { pollMs?: number }): Promise<unknown>;
  openSubscriptionSocket(): SubscriptionSocket;
  openRequestEventsSocket(): RequestEventsSocket;
  health(): Promise<unknown>;
}

export function createClient(options?: BrowserClientOptions): BrowserClient;

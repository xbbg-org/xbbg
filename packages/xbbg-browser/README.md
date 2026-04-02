# @xbbg/browser

Browser-safe client for the local `xbbg-server` bridge.

## Usage

```js
import { createClient } from '@xbbg/browser';

const client = createClient({ baseUrl: 'http://127.0.0.1:7878' });

const accepted = await client.request({
  service: '//blp/refdata',
  operation: 'ReferenceDataRequest',
  securities: ['XBTUSD Curncy'],
  fields: ['PX_LAST'],
  extractor: 'refdata',
});

const result = await client.waitForResult(accepted.requestId);

const sub = client.openSubscriptionSocket();
await sub.subscribe({
  topics: ['XBTUSD Curncy'],
  fields: ['LAST_PRICE', 'BID', 'ASK'],
});
sub.on('tick', (message) => console.log(message.rows));
```

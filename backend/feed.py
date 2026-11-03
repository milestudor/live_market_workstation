"""Small yfinance adapter: return on socket close, leaving retries to our supervisor.

Pinned yfinance 1.8.0's listener has its own indefinite reconnection loop. Owning
that loop here makes unavailable status and backoff observable. The two private
attributes below are intentionally isolated; recheck them when upgrading yfinance.
"""
import json
import yfinance as yf


class YahooStream(yf.AsyncWebSocket):
    async def listen(self, handler):
        async for raw in self._ws:
            envelope = json.loads(raw)
            if not envelope.get('message'):
                continue
            message = self._decode_message(envelope['message'])
            if 'error' in message:
                raise ValueError('Yahoo message could not be decoded')
            await handler(message)
        raise ConnectionError('Yahoo socket closed')

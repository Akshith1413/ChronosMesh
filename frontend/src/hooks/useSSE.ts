/**
 * ChronosMesh — useSSE hook for live real-time event streaming
 * Author: Guru Sai Prasad Reddy
 */

import { useState, useEffect } from 'react';
import api from '../services/api';
import { Event } from '../types';

export function useSSE(enabled: boolean = true) {
  const [events, setEvents] = useState<Event[]>([]);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const [heartbeat, setHeartbeat] = useState<any>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus('disconnected');
      return;
    }

    let es: EventSource | null = null;
    let reconnectTimeout: any = null;

    function connect() {
      setStatus('connecting');
      try {
        es = api.createEventSource();

        es.onopen = () => {
          setStatus('connected');
        };

        es.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data);
            if (parsed.type === 'event' && parsed.data) {
              setEvents((prev) => {
                const exists = prev.some((e) => e.event_id === parsed.data.event_id);
                if (exists) return prev;
                return [parsed.data, ...prev.slice(0, 49)];
              });
            } else if (parsed.type === 'heartbeat') {
              setHeartbeat(parsed);
            }
          } catch (err) {
            console.warn('SSE message parse error:', err);
          }
        };

        es.onerror = () => {
          setStatus('disconnected');
          if (es) {
            es.close();
            es = null;
          }
          reconnectTimeout = setTimeout(connect, 3000);
        };
      } catch (err) {
        setStatus('disconnected');
        reconnectTimeout = setTimeout(connect, 5000);
      }
    }

    connect();

    return () => {
      if (es) es.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [enabled]);

  return {
    events,
    status,
    heartbeat,
    clearEvents: () => setEvents([]),
  };
}

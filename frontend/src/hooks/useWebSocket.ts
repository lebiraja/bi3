import { useState, useEffect, useCallback, useRef } from 'react';
import type { WSMessage } from '../types/api';

interface UseWebSocketOptions {
  onMessage?: (message: WSMessage) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export const useWebSocket = (
  jobId: string | null,
  options: UseWebSocketOptions = {}
) => {
  const {
    onMessage,
    onError,
    onClose,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);

  const connect = useCallback(() => {
    if (!jobId || !shouldReconnectRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/${jobId}`);

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttemptsRef.current = 0; // Reset on successful connect
    };

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);
        setLastMessage(message);
        onMessage?.(message);
        
        // Stop reconnecting when job is done
        if (message.type === 'completed' || message.type === 'error') {
          shouldReconnectRef.current = false;
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.(error);
    };

    ws.onclose = () => {
      setIsConnected(false);
      onClose?.();

      // Only reconnect if allowed and under max attempts
      if (autoReconnect && jobId && shouldReconnectRef.current) {
        reconnectAttemptsRef.current += 1;
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, reconnectInterval);
        } else {
          console.warn('Max WebSocket reconnect attempts reached');
        }
      }
    };

    wsRef.current = ws;
  }, [jobId, onMessage, onError, onClose, autoReconnect, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  }, []);

  useEffect(() => {
    if (jobId) {
      shouldReconnectRef.current = true;
      reconnectAttemptsRef.current = 0;
      connect();
    }

    return () => {
      disconnect();
    };
  }, [jobId, connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    sendPing,
    disconnect,
  };
};

import { useState, useEffect, useCallback, useRef } from 'react';

export interface Message {
  type: 'student_answer' | 'instruction_response' | 'system_intervention' | 'stream_chunk';
  sender: 'student' | 'ai' | 'system';
  text?: string;
  message?: string; // from instruction_response
  concept_id?: string;
  timestamp: number;
}

export interface SystemAlert {
  action: string | null;
  reason: string | null;
  duration_minutes: number | null;
}

export const useTuringSocket = (studentId: string) => {
  const [chatHistory, setChatHistory] = useState<Message[]>([]);
  const [systemAlert, setSystemAlert] = useState<SystemAlert>({
    action: null,
    reason: null,
    duration_minutes: null,
  });
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(`ws://localhost:8040/ws/student/${studentId}`);
    socketRef.current = socket;

    socket.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket Connected');
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('WebSocket Message Received:', data);

      if (data.type === 'instruction_response') {
        const aiMessage: Message = {
          type: 'instruction_response',
          sender: 'ai',
          message: data.message || '',
          concept_id: data.concept_id,
          timestamp: Date.now(),
        };
        setChatHistory((prev) => [...prev, aiMessage]);
      } else if (data.type === 'stream_chunk') {
        setChatHistory((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.sender === 'ai') {
            const updatedMessage = {
              ...lastMessage,
              message: (lastMessage.message || '') + data.content,
            };
            return [...prev.slice(0, -1), updatedMessage];
          }
          return prev;
        });
      } else if (data.type === 'system_intervention') {
        setSystemAlert({
          action: data.action,
          reason: data.reason,
          duration_minutes: data.duration_minutes,
        });
      }
    };

    socket.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket Disconnected');
    };

    return () => {
      socket.close();
    };
  }, [studentId]);

  const sendMessage = useCallback((payload: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(payload));
      
      if (payload.type === 'student_answer') {
        const studentMessage: Message = {
          type: 'student_answer',
          sender: 'student',
          text: payload.answer_text,
          concept_id: payload.concept_id,
          timestamp: Date.now(),
        };
        setChatHistory((prev) => [...prev, studentMessage]);
      }
    }
  }, []);

  return { chatHistory, systemAlert, isConnected, sendMessage, setSystemAlert, setChatHistory };
};

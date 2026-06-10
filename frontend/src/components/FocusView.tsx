import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { Message } from '../hooks/useTuringSocket';
import MermaidDiagram from './MermaidDiagram';

interface FocusViewProps {
  chatHistory: Message[];
  sendMessage: (payload: any) => void;
  isConnected: boolean;
}

const FocusView: React.FC<FocusViewProps> = ({ chatHistory, sendMessage, isConnected }) => {
  const [answer, setAnswer] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatHistory]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim()) return;

    const payload = {
      type: 'student_answer',
      concept_id: chatHistory.filter(m => m.sender === 'ai').slice(-1)[0]?.concept_id || 'intro',
      answer_text: answer,
      response_time_seconds: 10, // Mocked for now
    };

    sendMessage(payload);
    setAnswer('');
  };

  return (
    <div className="flex h-[75vh] bg-slate-50">
      {/* Left Pane: Chat History */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 border-r border-slate-200 scroll-smooth">
        <div className="max-w-2xl mx-auto space-y-6">
          {chatHistory.map((msg, idx) => (
            <div
              key={idx}
              className={`p-6 rounded-2xl shadow-sm ${
                msg.sender === 'ai'
                  ? 'bg-white text-slate-800'
                  : 'bg-blue-600 text-white ml-auto max-w-[80%]'
              }`}
            >
              <div className="prose prose-slate max-w-none prose-headings:font-bold prose-p:leading-relaxed prose-pre:bg-slate-50 prose-pre:border prose-pre:border-slate-100">
                <ReactMarkdown 
                  remarkPlugins={[remarkMath]} 
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    code({ node, inline, className, children, ...props }: any) {
                      const match = /language-mermaid/.exec(className || '');
                      return !inline && match ? (
                        <MermaidDiagram chart={String(children).replace(/\n$/, '')} />
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    }
                  }}
                >
                  {msg.message || msg.text || ''}
                </ReactMarkdown>
              </div>
              <div className="text-xs mt-4 opacity-50">
                {new Date(msg.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))}
          {!isConnected && (
            <div className="text-center p-4 bg-red-50 text-red-600 rounded-lg">
              Connecting to TuringEd Brain...
            </div>
          )}
        </div>
      </div>

      {/* Right Pane: Input Form */}
      <div className="w-96 p-8 bg-white shadow-xl flex flex-col justify-center">
        <h2 className="text-2xl font-bold text-slate-800 mb-8 text-center">Your Turn</h2>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-500 mb-2">
              Type your answer below
            </label>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              className="w-full h-48 p-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none text-slate-700"
              placeholder="Explain your thinking..."
            />
          </div>
          <button
            type="submit"
            disabled={!isConnected || !answer.trim()}
            className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold rounded-xl shadow-lg shadow-blue-200 transition-all transform active:scale-95"
          >
            Submit Answer
          </button>
        </form>
      </div>
    </div>
  );
};

export default FocusView;

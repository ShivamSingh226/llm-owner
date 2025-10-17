import React from 'react';
import { useState, useEffect, useRef } from 'react';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import QuestionMarkRoundedIcon from '@mui/icons-material/QuestionMarkRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import CustomButton from './CustomButton';
import TypingIndicator from './TypingIndicator';
// f9ebff

const ChatWrapper = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState([
    {
      type: 'agent',
      text: `Welcome to Converse Copilot! I can help you draft message templates in seconds. Just tell me what you need. For example:
      \n• "Create a welcome message for new customers with a 15% discount"
      \n• "Draft an appointment reminder for tomorrow"
      \n• "Announce a weekend flash sale for Diwali"`,

      buttons: [],
    },
  ]);
  const messagesEndRef = useRef(null);
  const ws = useRef(null);
  useEffect(() => {
    // Connect to WebSocket backend
    ws.current = new WebSocket('ws://127.0.0.1:8765/ws');

    ws.current.onopen = () => console.log('✅ Connected to WebSocket server');

    ws.current.onmessage = (event) => {
      console.log('📩 Raw message:', event.data);

      let parsedMessages = [];

      try {
        // Handle cases like multiple JSON objects concatenated together
        const dataStr = event.data.trim();

        // Try to split possible multiple JSON chunks
        const jsonChunks = dataStr
          .split(/(?<=\})\s*(?=\{)/) // splits between }{
          .map((chunk) => chunk.trim())
          .filter(Boolean);

        jsonChunks.forEach((chunk) => {
          try {
            const obj = JSON.parse(chunk);
            parsedMessages.push(obj);
          } catch (err) {
            console.warn('⚠️ Could not parse chunk:', chunk);
            parsedMessages.push({ Body: chunk, Buttons: [] });
          }
        });
      } catch (err) {
        console.error('❌ Parsing error:', err);
        parsedMessages.push({ Body: event.data, Buttons: [] });
      }
      console.log('🛠️ Parsed messages:', parsedMessages);
      // Iterate through all parsed messages
      parsedMessages.forEach((data) => {
        const body = data.Body || data.body || data.content || 'No body found';
        const buttonsRaw = data.Buttons || data.buttons || [];

        // Normalize button data
        const buttons = Array.isArray(buttonsRaw)
          ? buttonsRaw
              .map((btn) => {
                const type = (btn.type || btn.Type || '')
                  .toLowerCase()
                  .replace(/[\s_]+/g, '');
                if (type === 'cta' || type === 'calltoaction') {
                  return {
                    type: 'CTA',
                    text: btn.text || btn.Text,
                    url: btn.url || btn.URL,
                    phone_number: btn.phone_number,
                    action: btn.Action,
                  };
                } else if (type === 'quickreply' || type === 'quick_reply') {
                  return { type: 'QUICK_REPLY', text: btn.text || btn.Text };
                }
                return null;
              })
              .filter(Boolean)
          : [];

        console.log('📝 Message body:', body);
        console.log('🔘 Buttons data:', buttons);

        // Construct and add bot message
        const botMsg = { type: 'agent', text: body, buttons };
        setMessages((prev) => [...prev, botMsg]);
        console.log('✅ Added bot message:', botMsg);
        setIsAgentTyping(false);
      });
    };

    ws.current.onerror = (err) => console.error('❌ WebSocket error:', err);
    ws.current.onclose = () => console.log('🔌 WebSocket disconnected');

    return () => ws.current?.close();
  }, []);

  useEffect(() => {
    console.log('The messages are: ', messages);
  }, [messages]);
  const [input, setInput] = useState('');
  const [isAgentTyping, setIsAgentTyping] = useState(false);
  const handleSend = (value) => {
    const messageToSend = value !== undefined ? value : input;
    if (messageToSend.trim() === '') return;
    

    const userMessage = { type: 'user', text: messageToSend, buttons: [] };
    setMessages((prev) => [...prev, userMessage]);
    setIsAgentTyping(true);

    // ✅ Send message over WebSocket if connected
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(messageToSend);
    } else {
      console.warn(
        '⚠️ WebSocket not open. Falling back to simulated response.'
      );
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          { type: 'agent', text: `You said: ${input}` },
        ]);
        setIsAgentTyping(false);
      }, 2000);
    }

    if(value===undefined)setInput('');
  };
  useEffect(() => {
    const interval = setInterval(() => {
      setIsExpanded((prev) => !prev);
    }, 800); // toggle every 1.5 seconds

    return () => clearInterval(interval);
  }, []);
  const handleQuickReply = (text) => {
    handleSend(text);
  };
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAgentTyping]);
  return (
    <div>
      <div className="flex justify-center items-center h-screen">
        <div className="rounded-lg shadow-lg p-6 w-full max-w-3/4 bg-gray-100">
          <div className="flex-col justify-between gap-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2 font-semibold text-xl text-gray-800">
                <DarkModeOutlinedIcon
                  style={{ fontSize: 24, color: '#ae00ff' }}
                />
                <span>Converse Copilot</span>
              </div>
              <div className="flex justify-end items-center gap-4">
                <h1 className="px-4 py-2 bg-gray-200 rounded-full font-semibold text-sm text-gray-600 inline-block">
                  Credits: 2035.8
                </h1>

                <div
                  className={`w-10 h-10 flex items-center justify-center rounded-full cursor-pointer transition-all duration-500 ease-in-out ${
                    isExpanded
                      ? 'bg-[#f9ebff] scale-110'
                      : 'bg-[#f3dcfe] scale-100'
                  }`}
                  style={{ transformOrigin: 'center' }}
                >
                  <QuestionMarkRoundedIcon
                    style={{
                      fontSize: 24,
                      color: isExpanded ? '#4b5563' : '#1f2937', // gray-600 vs gray-800
                      transition: 'color 0.5s ease-in-out',
                    }}
                  />
                </div>

                <div className="text-gray-500 hover:text-gray-800 cursor-pointer transition-colors duration-300">
                  <CloseRoundedIcon style={{ fontSize: 34 }} />
                </div>
              </div>
            </div>
            <hr className=" my-4 border-t border-gray-300 -mx-6" />
            <div
              className="flex-1 mt-4 overflow-y-auto space-y-2"
              style={{ maxHeight: '400px' }}
            >
              {/* Agent Message */}
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    msg.type === 'user'
                      ? 'justify-end'
                      : 'justify-start items-end'
                  } gap-2`}
                >
                  {msg.type === 'agent' && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 30,
                        height: 30,
                        borderRadius: '50%',
                        backgroundColor: '#ae00ff',
                      }}
                    >
                      <DarkModeOutlinedIcon
                        style={{ fontSize: 24, color: '#fff' }}
                      />
                    </div>
                  )}
                  <div
                    className={`px-4 py-2 rounded-lg max-w-md break-words ${
                      msg.type === 'agent'
                        ? 'bg-white text-gray-800'
                        : 'bg-blue-100 text-gray-800 max-w-xs'
                    }`}
                  >
                    {(msg.text || '').split('\n').map((line, i) => (
                      <p key={i}>{line}</p>
                    ))}
                    {msg.buttons && msg.buttons.length > 0 && (
                      <div className="mt-2 flex justify-start items-center gap-2">
                        {msg.buttons.map((btn, bIdx) => {
                          if (btn.type === 'QUICK_REPLY') {
                            return (
                              <button
                                key={bIdx}
                                onClick={() => handleQuickReply(btn.text)}
                                className="bg-gray-200 hover:bg-gray-300 text-gray-800 px-3 py-1 rounded-full text-sm w-fit"
                              >
                                {btn.text}
                              </button>
                            );
                          } else if (btn.type === 'CTA') {
                            const href = btn.url || `tel:${btn.phone_number}`;
                            return (
                              <a
                                key={bIdx}
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded-full text-sm inline-block w-fit"
                              >
                                {btn.text}
                              </a>
                            );
                          }
                          return null;
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* User Message */}
              {isAgentTyping && (
                <div className="flex justify-start items-end gap-2">
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 30,
                      height: 30,
                      borderRadius: '50%',
                      backgroundColor: '#ae00ff',
                    }}
                  >
                    <DarkModeOutlinedIcon
                      style={{ fontSize: 24, color: '#fff' }}
                    />
                  </div>
                  <div className="bg-white text-gray-800 px-4 py-2 rounded-lg max-w-md">
                    <TypingIndicator />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <hr className="my-4 border-t border-gray-300 -mx-6 mb-6" />
            <div className="bg-white px-6 py-4 -mx-6 -my-6">
              <div className="flex items-center justify-between gap-2">
                <input
                  type="text"
                  placeholder="Describe the message that you want to create..."
                  className="w-full px-4 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-yellow-500"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSend();
                    }
                  }}
                />
                <CustomButton
                  text="Send"
                  icon={() => {
                    null;
                  }}
                  variant="yellow"
                  onClick={() => handleSend()}
                  className="px-6 py-2"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatWrapper;

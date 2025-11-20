import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import Message from './Message'
import MemoryPanel from './MemoryPanel'
import './Chat.css'

const Chat = () => {
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [conversationId, setConversationId] = useState(null)
  const [userId] = useState(`user_${Date.now()}`)
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!inputMessage.trim()) return

    const userMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setLoading(true)

    try {
      const response = await axios.post('https://memory-ai-assistant1.vercel.app/chat', {
        message: inputMessage,
        user_id: userId,
        conversation_id: conversationId
      })

      const aiMessage = {
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date(response.data.timestamp),
        memories: response.data.memory_used
      }

      setMessages(prev => [...prev, aiMessage])
      setMemories(response.data.memory_used)
      
      if (!conversationId) {
        setConversationId(response.data.conversation_id)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        isError: true
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">🧠</span>
            <h1>Memory AI Assistant</h1>
          </div>
          <p>I remember our past conversations! Start chatting below.</p>
        </div>
      </div>

      <div className="chat-main">
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="welcome-message">
              <div className="welcome-icon">🤖</div>
              <h2>Welcome to your Memory AI Assistant!</h2>
              <p>I'll remember what we discuss and use that knowledge to help you better over time.</p>
              <div className="feature-list">
                <div className="feature">
                  <span>💬</span>
                  <span>Chat with AI that remembers</span>
                </div>
                <div className="feature">
                  <span>🧠</span>
                  <span>Long-term memory storage</span>
                </div>
                <div className="feature">
                  <span>🔍</span>
                  <span>Smart memory search</span>
                </div>
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <Message key={index} message={message} />
            ))
          )}
          {loading && (
            <div className="message assistant loading">
              <div className="message-avatar">🤖</div>
              <div className="message-content">
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <MemoryPanel memories={memories} />
      </div>

      <div className="input-container">
        <div className="input-wrapper">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message here... (Press Enter to send)"
            rows="1"
            disabled={loading}
          />
          <button 
            onClick={sendMessage} 
            disabled={loading || !inputMessage.trim()}
            className="send-button"
          >
            {loading ? (
              <div className="button-loading"></div>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/>
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Chat

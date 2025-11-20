import React from 'react'

const Message = ({ message }) => {
  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  return (
    <div className={`message ${message.role}`}>
      <div className="message-avatar">
        {message.role === 'user' ? '👤' : '🤖'}
      </div>
      <div className="message-content">
        <div className="message-text">
          {message.content}
        </div>
        <div className="message-time">
          {formatTime(message.timestamp)}
        </div>
        {message.memories && message.memories.length > 0 && (
          <div className="memory-indicator">
            🧠 Using {message.memories.length} memory item(s)
          </div>
        )}
        {message.isError && (
          <div className="error-indicator">
            ⚠️ Error occurred
          </div>
        )}
      </div>
    </div>
  )
}

export default Message

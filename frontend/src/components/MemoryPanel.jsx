import React from 'react'
import './MemoryPanel.css'

const MemoryPanel = ({ memories }) => {
  if (!memories || memories.length === 0) {
    return (
      <div className="memory-panel">
        <div className="memory-header">
          <div className="memory-icon">🧠</div>
          <h3>Active Memories</h3>
        </div>
        <div className="no-memories">
          <div className="empty-state">
            <div className="empty-icon">💭</div>
            <p>No relevant memories yet</p>
            <span>Start chatting to build memory!</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="memory-panel">
      <div className="memory-header">
        <div className="memory-icon">🧠</div>
        <h3>Active Memories</h3>
        <div className="memory-count">{memories.length}</div>
      </div>
      <div className="memories-list">
        {memories.map((memory, index) => (
          <div key={index} className="memory-item">
            <div className="memory-number">{index + 1}</div>
            <div className="memory-content">{memory}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default MemoryPanel

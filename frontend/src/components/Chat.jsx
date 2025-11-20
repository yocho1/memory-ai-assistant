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

  // FIX: Correct API URL
  const API_BASE_URL = 'https://memory-ai-assistant-wpwf.vercel.app'

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
      // FIX: Use correct URL with https://
      const response = await axios.post(`${API_BASE_URL}/chat`, {
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

  // ... rest of your component remains the same
}

export default Chat
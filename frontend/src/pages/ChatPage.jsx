import React, { useState, useRef, useEffect } from 'react'
import { Search, Send, Play, Clock, User, Bot, Loader2, Video, ChevronDown, FileVideo } from 'lucide-react'
import { searchVideos, getVideos } from '../services/api'
import ReactMarkdown from 'react-markdown'

function ChatPage() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '您好！我是猎影智能检索助手。\n\n请先选择要检索的视频，然后描述您要查找的目标特征。',
      videos: []
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [videos, setVideos] = useState([])
  const [selectedVideoId, setSelectedVideoId] = useState(null)
  const [showVideoDropdown, setShowVideoDropdown] = useState(false)
  const messagesEndRef = useRef(null)

  // 加载视频列表
  useEffect(() => {
    loadVideos()
  }, [])

  const loadVideos = async () => {
    try {
      const response = await getVideos()
      setVideos(response.videos || [])
      // 自动选择第一个视频
      if (response.videos?.length > 0 && !selectedVideoId) {
        setSelectedVideoId(response.videos[0].video_id)
      }
    } catch (err) {
      console.error('加载视频列表失败:', err)
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    if (!selectedVideoId) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '请先选择要检索的视频！',
        videos: []
      }])
      return
    }

    const userMessage = input.trim()
    setInput('')

    // 添加用户消息
    const selectedVideo = videos.find(v => v.video_id === selectedVideoId)
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      videos: [],
      videoName: selectedVideo?.video_id
    }])
    setLoading(true)

    try {
      // 调用搜索 API（指定视频ID）- 修复：使用正确的参数格式
      const response = await searchVideos(userMessage, {
        videoId: selectedVideoId,
        topK: 5,
        verifyTopN: 3
      })

      const results = response.results || []
      let assistantContent = ''
      const videoResults = []

      if (results.length === 0) {
        assistantContent = '抱歉，没有在视频中找到匹配的片段。\n\n请尝试其他关键词：\n• 车辆颜色（红色、白色、黑色）\n• 人员特征（头盔、衣服颜色）\n• 行为动作（骑行、行走）'
      } else {
        assistantContent = `在视频 **${selectedVideoId}** 中找到 **${results.length}** 个匹配片段：\n\n`

        results.forEach((result, index) => {
          assistantContent += `**片段 ${index + 1}** (${formatTime(result.start_time)} - ${formatTime(result.end_time)})\n`
          assistantContent += `${result.description?.substring(0, 100) || '无描述'}...\n`
          assistantContent += `相似度: ${(result.similarity * 100).toFixed(1)}%\n\n`

          videoResults.push({
            slice_id: result.slice_id,
            video_id: result.video_id,
            start_time: result.start_time,
            end_time: result.end_time,
            description: result.description,
            similarity: result.similarity,
            verification: result.visual_verification
          })
        })
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: assistantContent,
        videos: videoResults
      }])

    } catch (error) {
      console.error('Search error:', error)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `搜索出错: ${error.message}`,
        videos: []
      }])
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="space-y-4">
      {/* 标题和视频选择 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">智能检索</h1>
          <p className="text-sm text-gray-500 mt-1">选择视频后，输入自然语言描述进行检索</p>
        </div>

        {/* 视频选择器 */}
        <div className="relative">
          <button
            onClick={() => setShowVideoDropdown(!showVideoDropdown)}
            className="flex items-center space-x-2 px-4 py-2 bg-white border rounded-lg hover:bg-gray-50 min-w-[200px]"
          >
            <FileVideo className="h-5 w-5 text-primary-600" />
            <span className="flex-1 text-left truncate">
              {selectedVideoId || '选择视频'}
            </span>
            <ChevronDown className="h-4 w-4 text-gray-400" />
          </button>

          {showVideoDropdown && (
            <div className="absolute right-0 mt-2 w-64 bg-white border rounded-lg shadow-lg z-10">
              {videos.length === 0 ? (
                <div className="p-4 text-sm text-gray-500 text-center">
                  暂无已处理的视频
                </div>
              ) : (
                <div className="py-1">
                  {videos.map((video) => (
                    <button
                      key={video.video_id}
                      onClick={() => {
                        setSelectedVideoId(video.video_id)
                        setShowVideoDropdown(false)
                      }}
                      className={`w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center justify-between ${
                        selectedVideoId === video.video_id ? 'bg-primary-50 text-primary-700' : ''
                      }`}
                    >
                      <span className="truncate">{video.video_id}</span>
                      <span className="text-xs text-gray-400">{video.slice_count} 片段</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 当前选择的视频提示 */}
      {selectedVideoId && (
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-3 flex items-center space-x-2">
          <Video className="h-4 w-4 text-primary-600" />
          <span className="text-sm text-primary-700">
            当前检索视频: <strong>{selectedVideoId}</strong>
          </span>
          <span className="text-xs text-primary-500">
            ({videos.find(v => v.video_id === selectedVideoId)?.slice_count || 0} 个片段)
          </span>
        </div>
      )}

      {/* 消息区域 */}
      <div className="h-[calc(100vh-340px)] min-h-[400px] flex flex-col bg-white rounded-xl shadow-sm">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, index) => (
            <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-3xl ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-800'} rounded-lg p-4`}>
                <div className="flex items-start space-x-2">
                  {msg.role === 'assistant' && <Bot className="h-5 w-5 mt-0.5 text-gray-500 flex-shrink-0" />}
                  <div className="flex-1">
                    {/* 用户消息显示来源视频 */}
                    {msg.role === 'user' && msg.videoName && (
                      <div className="text-xs text-primary-200 mb-1">
                        检索视频: {msg.videoName}
                      </div>
                    )}
                    {/* Markdown 渲染 */}
                    <div className="text-sm prose prose-sm max-w-none">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {/* 视频片段卡片 */}
                    {msg.videos && msg.videos.length > 0 && (
                      <div className="mt-4 space-y-3">
                        {msg.videos.map((video, vIndex) => (
                          <VideoCard key={vIndex} video={video} index={vIndex + 1} />
                        ))}
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && <User className="h-5 w-5 mt-0.5 flex-shrink-0" />}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-lg p-4">
                <div className="flex items-center space-x-2 text-gray-600">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>正在分析视频库...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div className="border-t p-4">
          <div className="flex space-x-2">
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={selectedVideoId ? "描述您要查找的目标，如：戴白色头盔骑电动车的人" : "请先选择要检索的视频"}
                className="w-full p-3 pr-10 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
                rows="2"
                disabled={loading || !selectedVideoId}
              />
              <Search className="absolute right-3 top-3 h-5 w-5 text-gray-400" />
            </div>
            <button
              onClick={handleSend}
              disabled={loading || !input.trim() || !selectedVideoId}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              <Send className="h-5 w-5" />
              <span>搜索</span>
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            提示：可描述人物特征、车辆颜色、行为动作 | 按 Enter 发送
          </p>
        </div>
      </div>
    </div>
  )
}

// 视频卡片组件
function VideoCard({ video, index }) {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
      <div className="p-3 bg-gray-50 border-b flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Video className="h-4 w-4 text-primary-600" />
          <span className="font-medium text-sm">片段 {index}</span>
          <span className="text-xs text-gray-500 flex items-center">
            <Clock className="h-3 w-3 mr-1" />
            {formatTime(video.start_time)} - {formatTime(video.end_time)}
          </span>
        </div>
        <span className="text-xs bg-primary-100 text-primary-700 px-2 py-1 rounded">
          {(video.similarity * 100).toFixed(0)}% 匹配
        </span>
      </div>

      <div className="aspect-video bg-black relative max-h-[300px]">
        <video
          src={`/api/stream/${video.video_id}?start=${video.start_time}&end=${video.end_time}`}
          className="w-full h-full object-contain"
          controls
        />
      </div>

      <div className="p-3">
        <p className="text-xs text-gray-600 line-clamp-2">
          {video.description}
        </p>
        {video.verification && (
          <div className="mt-2 p-2 bg-yellow-50 rounded text-xs text-yellow-800">
            <strong>核实：</strong> {video.verification.substring(0, 100)}...
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatPage
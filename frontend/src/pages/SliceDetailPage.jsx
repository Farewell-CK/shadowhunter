import React, { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Clock, Database, Eye, ChevronDown, ChevronUp, Play, Pause, SkipBack, SkipForward, ArrowLeft, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getVideoSlices, getSlice, getStreamUrl } from '../services/api'

function SliceDetailPage() {
  const { videoId } = useParams()
  const [slices, setSlices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedSlice, setExpandedSlice] = useState(null)
  const [selectedSlice, setSelectedSlice] = useState(null)
  const [playingSlice, setPlayingSlice] = useState(null)
  const videoRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    loadSlices()
  }, [videoId])

  const loadSlices = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getVideoSlices(videoId)
      setSlices(response.slices || [])
    } catch (err) {
      setError(err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  const loadSliceDetail = async (sliceId) => {
    try {
      const detail = await getSlice(sliceId)
      setSelectedSlice(detail)
    } catch (err) {
      console.error('加载切片详情失败:', err)
    }
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const toggleSlice = (sliceId) => {
    if (expandedSlice === sliceId) {
      setExpandedSlice(null)
    } else {
      setExpandedSlice(sliceId)
      loadSliceDetail(sliceId)
    }
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/video" className="p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">视频切片详情</h1>
            <p className="text-gray-500">视频 ID: {videoId}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Database className="h-4 w-4" />
          <span>共 {slices.length} 个切片</span>
        </div>
      </div>

      {/* 加载状态 */}
      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
          <p className="mt-4 text-gray-500">加载切片数据...</p>
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          {error}
        </div>
      )}

      {/* 切片列表 */}
      {!loading && slices.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          该视频暂无切片数据
        </div>
      )}

      {/* 切片卡片列表 */}
      <div className="space-y-3">
        {slices.map((slice, index) => (
          <div
            key={slice.slice_id}
            className="bg-white rounded-lg shadow-sm border overflow-hidden"
          >
            {/* 卡片头部 */}
            <div
              className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
              onClick={() => toggleSlice(slice.slice_id)}
            >
              <div className="flex items-center space-x-4">
                <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center text-primary-700 font-medium text-sm">
                  {index + 1}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <Clock className="h-4 w-4 text-gray-400" />
                    <span className="font-medium">
                      {formatTime(slice.start_time)} - {formatTime(slice.end_time)}
                    </span>
                    <span className="text-sm text-gray-400">
                      ({slice.duration?.toFixed(1)}s)
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                    {slice.description || '暂无描述'}
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-right text-sm">
                  <div className="text-gray-400">向量维度</div>
                  <div className="font-medium">{slice.embedding_dimension || 0}</div>
                </div>
                {expandedSlice === slice.slice_id ? (
                  <ChevronUp className="h-5 w-5 text-gray-400" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-gray-400" />
                )}
              </div>
            </div>

            {/* 展开详情 */}
            {expandedSlice === slice.slice_id && (
              <div className="border-t bg-gray-50 p-4 space-y-4">
                {/* 完整描述 */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">视频描述</h4>
                  <p className="text-sm text-gray-600 bg-white p-3 rounded border">
                    {slice.description || '暂无描述'}
                  </p>
                </div>

                {/* 向量信息 */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">向量数据库信息</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div className="bg-white p-3 rounded border">
                      <div className="text-gray-400">切片 ID</div>
                      <div className="font-mono text-xs mt-1 break-all">{slice.slice_id}</div>
                    </div>
                    <div className="bg-white p-3 rounded border">
                      <div className="text-gray-400">向量维度</div>
                      <div className="font-medium mt-1">{slice.embedding_dimension || 0}</div>
                    </div>
                    <div className="bg-white p-3 rounded border">
                      <div className="text-gray-400">开始时间</div>
                      <div className="font-medium mt-1">{slice.start_time?.toFixed(2)}s</div>
                    </div>
                    <div className="bg-white p-3 rounded border">
                      <div className="text-gray-400">结束时间</div>
                      <div className="font-medium mt-1">{slice.end_time?.toFixed(2)}s</div>
                    </div>
                  </div>
                </div>

                {/* 向量预览 */}
                {slice.embedding_preview && slice.embedding_preview.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">向量前 10 维预览</h4>
                    <div className="bg-white p-3 rounded border font-mono text-xs overflow-x-auto">
                      [{slice.embedding_preview.map((v) => v.toFixed(4)).join(', ')}, ...]
                    </div>
                  </div>
                )}

                {/* 元数据 */}
                {slice.metadata && Object.keys(slice.metadata).length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">元数据</h4>
                    <div className="bg-white p-3 rounded border text-sm">
                      <pre className="text-xs text-gray-600 overflow-x-auto">
                        {JSON.stringify(slice.metadata, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex space-x-2 pt-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setPlayingSlice(slice)
                    }}
                    className="flex items-center space-x-1 px-3 py-1.5 bg-primary-600 text-white rounded text-sm hover:bg-primary-700"
                  >
                    <Play className="h-4 w-4" />
                    <span>播放片段</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      loadSliceDetail(slice.slice_id)
                    }}
                    className="flex items-center space-x-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200"
                  >
                    <Eye className="h-4 w-4" />
                    <span>查看详情</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 视频播放弹窗 */}
      {playingSlice && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">
                片段播放: {formatTime(playingSlice.start_time)} - {formatTime(playingSlice.end_time)}
              </h3>
              <button
                onClick={() => {
                  setPlayingSlice(null)
                  setIsPlaying(false)
                }}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4">
              <div className="aspect-video bg-black rounded-lg overflow-hidden">
                <video
                  ref={videoRef}
                  src={getStreamUrl(playingSlice.video_id, playingSlice.start_time, playingSlice.end_time)}
                  className="w-full h-full object-contain"
                  onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
                  onLoadedMetadata={(e) => setDuration(e.target.duration)}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onEnded={() => setIsPlaying(false)}
                  autoPlay
                />
              </div>
              {/* 播放控制 */}
              <div className="flex items-center justify-center space-x-4 mt-4">
                <button
                  onClick={() => {
                    if (videoRef.current) {
                      videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 5)
                    }
                  }}
                  className="p-2 rounded-lg hover:bg-gray-100"
                  title="后退5秒"
                >
                  <SkipBack className="h-5 w-5" />
                </button>
                <button
                  onClick={() => {
                    if (videoRef.current) {
                      if (isPlaying) {
                        videoRef.current.pause()
                      } else {
                        videoRef.current.play()
                      }
                    }
                  }}
                  className="p-3 rounded-full bg-primary-600 text-white hover:bg-primary-700"
                >
                  {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                </button>
                <button
                  onClick={() => {
                    if (videoRef.current) {
                      videoRef.current.currentTime = Math.min(duration, videoRef.current.currentTime + 5)
                    }
                  }}
                  className="p-2 rounded-lg hover:bg-gray-100"
                  title="前进5秒"
                >
                  <SkipForward className="h-5 w-5" />
                </button>
              </div>
              <div className="text-center text-sm text-gray-500 mt-2">
                {formatTime(currentTime)} / {formatTime(duration)}
              </div>
              {/* 描述 */}
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">{playingSlice.description}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 详情弹窗 */}
      {selectedSlice && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">切片详情</h3>
              <button
                onClick={() => setSelectedSlice(null)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm text-gray-500">切片 ID</div>
                  <div className="font-mono text-sm break-all">{selectedSlice.slice_id}</div>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm text-gray-500">视频 ID</div>
                  <div className="font-mono text-sm">{selectedSlice.video_id}</div>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm text-gray-500">开始时间</div>
                  <div className="font-medium">{selectedSlice.start_time?.toFixed(2)}s</div>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm text-gray-500">结束时间</div>
                  <div className="font-medium">{selectedSlice.end_time?.toFixed(2)}s</div>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm text-gray-500">时长</div>
                  <div className="font-medium">{selectedSlice.duration?.toFixed(2)}s</div>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="text-sm text-gray-500">向量维度</div>
                  <div className="font-medium">{selectedSlice.embedding_dimension || 0}</div>
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500 mb-2">描述</div>
                <div className="bg-gray-50 p-3 rounded-lg text-sm">{selectedSlice.description}</div>
              </div>
              {selectedSlice.metadata && (
                <div>
                  <div className="text-sm text-gray-500 mb-2">元数据</div>
                  <pre className="bg-gray-50 p-3 rounded-lg text-xs overflow-auto max-h-60">
                    {JSON.stringify(selectedSlice.metadata, null, 2)}
                  </pre>
                </div>
              )}
              {selectedSlice.embedding_preview && (
                <div>
                  <div className="text-sm text-gray-500 mb-2">向量前10维</div>
                  <div className="bg-gray-50 p-3 rounded-lg font-mono text-xs overflow-auto">
                    [{selectedSlice.embedding_preview.map((v) => v.toFixed(4)).join(', ')}, ...]
                  </div>
                </div>
              )}
              <div className="flex justify-end pt-2">
                <button
                  onClick={() => {
                    const slice = selectedSlice
                    setSelectedSlice(null)
                    setPlayingSlice(slice)
                  }}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                >
                  播放此片段
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SliceDetailPage
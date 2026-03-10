import { useState, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Filter, Clock, Eye, Play, Pause, SkipBack, SkipForward } from 'lucide-react'
import ResultCard from '../components/ResultCard'
import { searchVideos, getStreamUrl } from '../services/api'

function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''

  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedResult, setSelectedResult] = useState(null)

  // 视频播放器状态
  const videoRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // 搜索处理
  const handleSearch = async (e) => {
    e?.preventDefault()

    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResults([])
    setSelectedResult(null)

    // 更新 URL 参数
    setSearchParams({ q: query })

    try {
      const response = await searchVideos(query)
      setResults(response.results || [])
    } catch (err) {
      setError(err.message || '搜索失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  // 格式化时间
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="space-y-6">
      {/* 搜索栏 */}
      <section className="bg-white rounded-xl shadow-sm p-6">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex space-x-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="描述您要查找的目标，例如：骑电动车戴白色头盔的人..."
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {loading ? '搜索中...' : '搜索'}
            </button>
          </div>

          {/* 快速特征筛选 */}
          <div className="flex items-center space-x-2 text-sm">
            <Filter className="h-4 w-4 text-gray-400" />
            <span className="text-gray-500">快速筛选：</span>
            {['白色头盔', '绿色上衣', '电动车', '黑色背包'].map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => setQuery((prev) => prev ? `${prev} ${tag}` : tag)}
                className="px-2 py-1 bg-gray-100 rounded text-gray-600 hover:bg-primary-50 hover:text-primary-700"
              >
                {tag}
              </button>
            ))}
          </div>
        </form>
      </section>

      {/* 搜索结果 */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* 结果列表 */}
        <div className="lg:col-span-2 space-y-4">
          {error && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg">
              {error}
            </div>
          )}

          {loading && (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
              <p className="mt-4 text-gray-500">正在分析视频...</p>
            </div>
          )}

          {!loading && results.length === 0 && query && (
            <div className="text-center py-12 text-gray-500">
              未找到匹配的视频片段，请尝试其他关键词
            </div>
          )}

          {!loading && results.length === 0 && !query && (
            <div className="text-center py-12 text-gray-500">
              输入描述开始搜索
            </div>
          )}

          {/* 结果卡片 */}
          {results.map((result) => (
            <ResultCard
              key={result.slice_id}
              result={result}
              isSelected={selectedResult?.slice_id === result.slice_id}
              onClick={() => setSelectedResult(result)}
            />
          ))}
        </div>

        {/* 详情面板 */}
        <div className="lg:col-span-1">
          {selectedResult ? (
            <div className="bg-white rounded-xl shadow-sm p-6 sticky top-6">
              <h3 className="text-lg font-semibold mb-4">分析报告</h3>

              {/* 时间信息 */}
              <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center text-sm text-gray-600">
                  <Clock className="h-4 w-4 mr-2" />
                  <span>
                    {formatTime(selectedResult.start_time)} - {formatTime(selectedResult.end_time)}
                  </span>
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  相似度: {(selectedResult.similarity * 100).toFixed(1)}%
                </div>
              </div>

              {/* 视频描述 */}
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">视频描述</h4>
                <p className="text-sm text-gray-600">
                  {selectedResult.description}
                </p>
              </div>

              {/* 视觉核实报告 */}
              {selectedResult.visual_verification && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                    <Eye className="h-4 w-4 mr-1" />
                    视觉核实
                  </h4>
                  <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg">
                    {selectedResult.visual_verification}
                  </div>
                </div>
              )}

              {/* 视频播放器 */}
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">视频片段</h4>
                <div className="video-container aspect-video bg-black rounded-lg overflow-hidden">
                  <video
                    ref={videoRef}
                    src={getStreamUrl(selectedResult.video_id, selectedResult.start_time, selectedResult.end_time)}
                    className="w-full h-full object-contain"
                    onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
                    onLoadedMetadata={(e) => setDuration(e.target.duration)}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onEnded={() => setIsPlaying(false)}
                  />
                </div>

                {/* 播放控制 */}
                <div className="flex items-center justify-center space-x-4 mt-3">
                  <button
                    onClick={() => {
                      if (videoRef.current) {
                        videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 5)
                      }
                    }}
                    className="p-2 rounded-lg hover:bg-gray-100"
                    title="后退5秒"
                  >
                    <SkipBack className="h-4 w-4" />
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
                    title={isPlaying ? '暂停' : '播放'}
                  >
                    {isPlaying ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
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
                    <SkipForward className="h-4 w-4" />
                  </button>
                </div>

                {/* 时间显示 */}
                <div className="text-center text-xs text-gray-500 mt-2">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="flex space-x-2 mt-4">
                <button
                  onClick={() => {
                    if (videoRef.current) {
                      videoRef.current.currentTime = 0
                      videoRef.current.play()
                    }
                  }}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm"
                >
                  重新播放
                </button>
                <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm">
                  导出报告
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-xl p-6 text-center text-gray-500">
              选择一个结果查看详情
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SearchPage
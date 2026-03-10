import { useState, useRef } from 'react'
import { Upload, Search, FileVideo, X, Play, Clock, AlertCircle, CheckCircle } from 'lucide-react'
import { directMatchUpload, getTaskStatus, getStreamUrl } from '../services/api'

function DirectMatchPage() {
  const [files, setFiles] = useState([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState(null)
  const [selectedResult, setSelectedResult] = useState(null)

  const fileInputRef = useRef(null)
  const folderInputRef = useRef(null)
  const videoRef = useRef(null)

  // 支持的格式
  const supportedFormats = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']

  // 处理文件选择
  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files)
    const videoFiles = selectedFiles.filter(file =>
      supportedFormats.some(ext => file.name.toLowerCase().endsWith(ext))
    )
    setFiles(prev => [...prev, ...videoFiles])
  }

  // 处理文件夹选择
  const handleFolderSelect = (e) => {
    const selectedFiles = Array.from(e.target.files)
    const videoFiles = selectedFiles.filter(file =>
      supportedFormats.some(ext => file.name.toLowerCase().endsWith(ext))
    )
    setFiles(prev => [...prev, ...videoFiles])
  }

  // 移除文件
  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  // 清空所有文件
  const clearFiles = () => {
    setFiles([])
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (folderInputRef.current) folderInputRef.current.value = ''
  }

  // 执行直接匹配
  const handleMatch = async () => {
    if (files.length === 0) {
      setError('请先选择视频文件')
      return
    }
    if (!query.trim()) {
      setError('请输入查询描述')
      return
    }

    setLoading(true)
    setError(null)
    setResults([])
    setSelectedResult(null)
    setProgress({ message: '正在上传视频...', percent: 0 })

    try {
      // 调用直接匹配 API
      const response = await directMatchUpload(files, query, {
        topK: 20,
        storeResults: true,
      })

      setResults(response.results || [])
      setProgress(null)

      if (response.results.length === 0) {
        setError('未找到匹配的视频片段')
      }
    } catch (err) {
      setError(err.message || '匹配失败，请重试')
      setProgress(null)
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

  // 获取置信度颜色
  const getConfidenceColor = (confidence) => {
    if (confidence >= 80) return 'text-green-600 bg-green-50'
    if (confidence >= 50) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  return (
    <div className="space-y-6">
      {/* 标题说明 */}
      <section className="bg-white rounded-xl shadow-sm p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">直接视频匹配</h1>
        <p className="text-gray-600">
          上传视频并输入目标描述，系统将精确分析每个视频片段，找出最匹配的结果。
          <span className="text-primary-600 font-medium">适用于公安侦查等精确查找场景。</span>
        </p>
      </section>

      {/* 上传区域 */}
      <section className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold mb-4">1. 选择视频</h2>

        <div className="grid md:grid-cols-2 gap-4 mb-4">
          {/* 文件上传按钮 */}
          <div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="video/*"
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
            >
              <Upload className="h-8 w-8 mx-auto mb-2 text-gray-400" />
              <p className="text-gray-600">点击选择视频文件</p>
              <p className="text-sm text-gray-400 mt-1">支持 mp4, avi, mov, mkv 等格式</p>
            </button>
          </div>

          {/* 文件夹上传按钮 */}
          <div>
            <input
              ref={folderInputRef}
              type="file"
              multiple
              // webkitdirectory 属性允许选择文件夹
              {...{ webkitdirectory: '', directory: '' }}
              onChange={handleFolderSelect}
              className="hidden"
            />
            <button
              onClick={() => folderInputRef.current?.click()}
              className="w-full p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
            >
              <FileVideo className="h-8 w-8 mx-auto mb-2 text-gray-400" />
              <p className="text-gray-600">点击选择文件夹</p>
              <p className="text-sm text-gray-400 mt-1">自动识别文件夹中的所有视频</p>
            </button>
          </div>
        </div>

        {/* 已选文件列表 */}
        {files.length > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">已选择 {files.length} 个文件</span>
              <button
                onClick={clearFiles}
                className="text-sm text-red-600 hover:text-red-700"
              >
                清空全部
              </button>
            </div>
            <div className="max-h-40 overflow-y-auto border rounded-lg">
              {files.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-2 border-b last:border-b-0 hover:bg-gray-50"
                >
                  <div className="flex items-center space-x-2">
                    <FileVideo className="h-4 w-4 text-gray-400" />
                    <span className="text-sm truncate max-w-xs">{file.name}</span>
                    <span className="text-xs text-gray-400">
                      {(file.size / 1024 / 1024).toFixed(1)} MB
                    </span>
                  </div>
                  <button
                    onClick={() => removeFile(index)}
                    className="p-1 hover:bg-gray-200 rounded"
                  >
                    <X className="h-4 w-4 text-gray-400" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 查询输入 */}
      <section className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold mb-4">2. 输入目标描述</h2>

        <div className="space-y-4">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="描述您要查找的目标，例如：&#10;- 偷电瓶的人&#10;- 骑电动车戴白色头盔的人&#10;- 穿黑色上衣背双肩包的男子"
            className="w-full p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none"
            rows={3}
          />

          {/* 快速输入建议 */}
          <div className="flex flex-wrap gap-2">
            <span className="text-sm text-gray-500">快速输入：</span>
            {['偷电瓶的人', '骑电动车的人', '戴头盔的人', '穿黑色上衣的人'].map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => setQuery(suggestion)}
                className="px-3 py-1 text-sm bg-gray-100 rounded-full hover:bg-primary-50 hover:text-primary-700"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        {/* 开始匹配按钮 */}
        <div className="mt-6">
          <button
            onClick={handleMatch}
            disabled={loading || files.length === 0}
            className="w-full py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                <span>{progress?.message || '正在分析...'}</span>
              </>
            ) : (
              <>
                <Search className="h-5 w-5" />
                <span>开始直接匹配</span>
              </>
            )}
          </button>
        </div>
      </section>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg flex items-center space-x-2">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      )}

      {/* 匹配结果 */}
      {results.length > 0 && (
        <section className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">
            匹配结果 ({results.length} 个)
          </h2>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* 结果列表 */}
            <div className="lg:col-span-2 space-y-4">
              {results.map((result, index) => (
                <div
                  key={result.slice_id}
                  onClick={() => setSelectedResult(result)}
                  className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                    selectedResult?.slice_id === result.slice_id
                      ? 'border-primary-500 bg-primary-50'
                      : 'hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="font-medium">#{index + 1}</span>
                        <span className={`text-xs px-2 py-1 rounded ${getConfidenceColor(result.confidence)}`}>
                          置信度: {result.confidence.toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{result.description}</p>
                      <div className="flex items-center space-x-4 text-xs text-gray-400">
                        <span className="flex items-center">
                          <Clock className="h-3 w-3 mr-1" />
                          {formatTime(result.start_time)} - {formatTime(result.end_time)}
                        </span>
                        <span>视频: {result.video_id}</span>
                      </div>
                    </div>
                    {result.confidence >= 80 && (
                      <CheckCircle className="h-6 w-6 text-green-500" />
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* 详情面板 */}
            <div className="lg:col-span-1">
              {selectedResult ? (
                <div className="sticky top-6 space-y-4">
                  {/* 视频播放器 */}
                  <div className="aspect-video bg-black rounded-lg overflow-hidden">
                    <video
                      ref={videoRef}
                      src={getStreamUrl(
                        selectedResult.video_id,
                        selectedResult.start_time,
                        selectedResult.end_time
                      )}
                      className="w-full h-full object-contain"
                      controls
                    />
                  </div>

                  {/* 匹配详情 */}
                  <div className="p-4 bg-gray-50 rounded-lg space-y-3">
                    <div>
                      <span className="text-xs text-gray-500">置信度</span>
                      <div className="flex items-center space-x-2 mt-1">
                        <div className="flex-1 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-primary-600 h-2 rounded-full"
                            style={{ width: `${selectedResult.confidence}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium">{selectedResult.confidence.toFixed(0)}%</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-xs text-gray-500">匹配理由</span>
                      <p className="text-sm text-gray-700 mt-1">{selectedResult.reason}</p>
                    </div>

                    <div>
                      <span className="text-xs text-gray-500">时间范围</span>
                      <p className="text-sm text-gray-700 mt-1">
                        {formatTime(selectedResult.start_time)} - {formatTime(selectedResult.end_time)}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-gray-50 rounded-lg p-6 text-center text-gray-500">
                  选择一个结果查看详情
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

export default DirectMatchPage
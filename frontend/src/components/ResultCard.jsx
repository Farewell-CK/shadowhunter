import React from 'react'
import { Clock, Eye, ChevronRight } from 'lucide-react'

function ResultCard({ result, isSelected, onClick }) {
  // 格式化时间
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // 相似度颜色
  const getSimilarityColor = (similarity) => {
    if (similarity >= 0.8) return 'text-green-600 bg-green-50'
    if (similarity >= 0.6) return 'text-yellow-600 bg-yellow-50'
    return 'text-gray-600 bg-gray-50'
  }

  return (
    <div
      onClick={onClick}
      className={`result-card cursor-pointer border-2 transition-all ${
        isSelected
          ? 'border-primary-500 ring-2 ring-primary-200'
          : 'border-transparent hover:border-gray-200'
      }`}
    >
      {/* 头部信息 */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-2">
          <Clock className="h-4 w-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-900">
            {formatTime(result.start_time)} - {formatTime(result.end_time)}
          </span>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${getSimilarityColor(result.similarity)}`}>
          {(result.similarity * 100).toFixed(1)}% 匹配
        </span>
      </div>

      {/* 描述 */}
      <p className="text-gray-600 text-sm mb-3 line-clamp-2">
        {result.description || '暂无描述'}
      </p>

      {/* 视觉核实状态 */}
      {result.visual_verification && (
        <div className="flex items-center text-xs text-primary-600 bg-primary-50 px-2 py-1 rounded">
          <Eye className="h-3 w-3 mr-1" />
          <span>已完成视觉核实</span>
        </div>
      )}

      {/* 视频ID */}
      <div className="mt-3 pt-3 border-t text-xs text-gray-400">
        视频: {result.video_id}
      </div>
    </div>
  )
}

export default ResultCard
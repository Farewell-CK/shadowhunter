import React from 'react'

function Timeline({ duration, currentTime, onSeek, slices = [] }) {
  // 点击时间轴跳转
  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percentage = x / rect.width
    const time = percentage * duration
    onSeek(time)
  }

  // 计算当前位置百分比
  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0

  // 片段标记
  const renderSliceMarkers = () => {
    if (!slices || slices.length === 0 || duration <= 0) return null

    return slices.map((slice, index) => {
      const startPercent = (slice.start_time / duration) * 100
      const widthPercent = ((slice.end_time - slice.start_time) / duration) * 100

      return (
        <div
          key={slice.slice_id || index}
          className="absolute top-0 h-full bg-primary-200 opacity-50 hover:opacity-80 cursor-pointer"
          style={{
            left: `${startPercent}%`,
            width: `${widthPercent}%`,
          }}
          onClick={(e) => {
            e.stopPropagation()
            onSeek(slice.start_time)
          }}
          title={`${slice.start_time.toFixed(1)}s - ${slice.end_time.toFixed(1)}s`}
        />
      )
    })
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-gray-700">时间轴</label>

      {/* 时间轴容器 */}
      <div
        className="relative h-8 bg-gray-200 rounded cursor-pointer overflow-hidden"
        onClick={handleClick}
      >
        {/* 片段标记 */}
        {renderSliceMarkers()}

        {/* 进度条 */}
        <div
          className="absolute top-0 left-0 h-full bg-primary-600 transition-all"
          style={{ width: `${progressPercent}%` }}
        />

        {/* 当前位置指示器 */}
        <div
          className="absolute top-0 w-1 h-full bg-red-500"
          style={{ left: `${progressPercent}%` }}
        />
      </div>

      {/* 时间刻度 */}
      <div className="flex justify-between text-xs text-gray-400">
        <span>0:00</span>
        <span>{formatTime(duration / 4)}</span>
        <span>{formatTime(duration / 2)}</span>
        <span>{formatTime((duration * 3) / 4)}</span>
        <span>{formatTime(duration)}</span>
      </div>
    </div>
  )
}

// 格式化时间
function formatTime(seconds) {
  if (!seconds || seconds <= 0) return '0:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export default Timeline
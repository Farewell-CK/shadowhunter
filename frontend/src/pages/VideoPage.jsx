import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Upload, Play, Pause, SkipBack, SkipForward, Trash2, Loader, RefreshCw, CheckCircle2 } from 'lucide-react'
import Timeline from '../components/Timeline'
import { uploadVideo, processVideo, getTaskStatus, getVideos, deleteVideo, getConfig } from '../services/api'

// 全局任务状态存储
const globalTasks = new Map()

function VideoPage() {
  const { videoId } = useParams()
  const navigate = useNavigate()
  const videoRef = useRef(null)

  const [videos, setVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [taskStatus, setTaskStatus] = useState(null)
  const [currentTaskId, setCurrentTaskId] = useState(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  // --- 智能分析配置状态 ---
  const [enableMotion, setEnableMotion] = useState(true)
  const [enableObject, setEnableObject] = useState(true)
  const [smartScan, setSmartScan] = useState(true)
  const [motionThreshold, setMotionThreshold] = useState(0.01)
  const [availableObjects, setAvailableObjects] = useState([])
  const [selectedObjects, setSelectedObjects] = useState([])
  const [showAdvanced, setShowAdvanced] = useState(false)

  // 加载视频列表与初始配置
  useEffect(() => {
    loadVideos()
    fetchInitialConfig()
    restoreTasks()
  }, [])

  const fetchInitialConfig = async () => {
    try {
      const config = await getConfig()
      setAvailableObjects(config.available_objects || [])
      setSelectedObjects(config.required_objects || [])
      setEnableMotion(config.enable_motion_detection)
      setEnableObject(config.enable_object_detection)
      if (config.motion_threshold) setMotionThreshold(config.motion_threshold)
    } catch (err) {
      console.error('加载系统配置失败:', err)
    }
  }

  const toggleObjectSelection = (obj) => {
    setSelectedObjects(prev => 
      prev.includes(obj) 
        ? prev.filter(item => item !== obj)
        : [...prev, obj]
    )
  }

  // 上传并启动处理
  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const result = await uploadVideo(file)
      setUploading(false)

      // 开始处理，传递所有配置参数
      setProcessing(true)
      const processResult = await processVideo(
        result.file_path, 
        result.video_id, 
        selectedObjects,
        enableMotion,
        enableObject,
        motionThreshold,
        smartScan
      )

      pollTaskStatus(processResult.task_id)
    } catch (err) {
      console.error('上传或处理启动失败:', err)
      setUploading(false)
      setProcessing(false)
      alert('操作失败: ' + err.message)
    }
  }

  // --- UI 组件部分 ---
  return (
    <div className="space-y-6">
      <section className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center">
          <Upload className="w-5 h-5 mr-2 text-primary-600" />
          视频上传与智能分析配置
        </h2>

        {/* 配置面板 */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex flex-wrap items-center gap-6 mb-4">
            <label className="flex items-center cursor-pointer group">
              <input 
                type="checkbox" 
                checked={enableMotion} 
                onChange={(e) => setEnableMotion(e.target.checked)}
                className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
              />
              <span className="ml-2 text-sm font-medium text-gray-700 group-hover:text-primary-600 transition-colors">
                开启 OpenCV 运动检测 (过滤静止画面)
              </span>
            </label>

            <label className="flex items-center cursor-pointer group">
              <input 
                type="checkbox" 
                checked={enableObject} 
                onChange={(e) => setEnableObject(e.target.checked)}
                className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
              />
              <span className="ml-2 text-sm font-medium text-gray-700 group-hover:text-primary-600 transition-colors">
                开启 YOLO 目标初筛 (仅分析人/车)
              </span>
            </label>

            <label className="flex items-center cursor-pointer group">
              <input 
                type="checkbox" 
                checked={smartScan} 
                onChange={(e) => setSmartScan(e.target.checked)}
                className="w-4 h-4 text-orange-600 rounded focus:ring-orange-500"
              />
              <span className="ml-2 text-sm font-medium text-gray-700 group-hover:text-orange-600 transition-colors font-semibold">
                智能事件扫描模式 (解决边缘遗漏)
              </span>
            </label>

            <button 
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-primary-600 hover:underline"
            >
              {showAdvanced ? "收起高级设置" : "调优阈值参数"}
            </button>
          </div>

          {/* 高级设置：阈值调整 */}
          {showAdvanced && (
            <div className="mb-4 p-3 bg-white rounded border border-gray-200 animate-in fade-in duration-200">
              <div className="flex items-center space-x-4">
                <span className="text-xs text-gray-500">运动面积阈值:</span>
                <input 
                  type="range" min="0.001" max="0.1" step="0.001"
                  value={motionThreshold}
                  onChange={(e) => setMotionThreshold(parseFloat(e.target.value))}
                  className="w-48 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
                />
                <span className="text-sm font-mono text-primary-700">{(motionThreshold * 100).toFixed(2)}%</span>
                <p className="text-xs text-gray-400">（数值越小越灵敏，建议 1% 即 0.01）</p>
              </div>
            </div>
          )}

          {/* 目标勾选 (仅在开启目标检测时显示) */}
          {enableObject && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">需识别的目标类型:</h3>
              <div className="flex flex-wrap gap-2">
                {availableObjects.map(obj => {
                  const isSelected = selectedObjects.includes(obj)
                  return (
                    <button
                      key={obj}
                      onClick={() => toggleObjectSelection(obj)}
                      className={`flex items-center px-3 py-1 rounded-full text-xs transition-all border ${
                        isSelected 
                          ? 'bg-primary-600 text-white border-primary-600 shadow-sm' 
                          : 'bg-white text-gray-600 border-gray-300 hover:border-primary-400'
                      }`}
                    >
                      {isSelected && <CheckCircle2 className="w-3 h-3 mr-1" />}
                      {obj}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center bg-white hover:bg-gray-50 transition-colors">
          <input
            type="file"
            accept="video/*"
            onChange={handleUpload}
            className="hidden"
            id="video-upload"
            disabled={uploading || processing}
          />
          <label
            htmlFor="video-upload"
            className={`cursor-pointer ${uploading || processing ? 'opacity-50' : ''}`}
          >
            <Upload className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600">
              {uploading ? '上传中...' : processing ? '处理中...' : '点击或拖拽上传视频文件'}
            </p>
            <p className="text-sm text-gray-400 mt-2">
              支持 MP4, WebM, MOV 格式
            </p>
          </label>
        </div>

        {/* 处理进度 */}
        {taskStatus && (processing || taskStatus.status !== 'pending') && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-3">
            {/* 总体进度 */}
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">{taskStatus.message}</span>
              <span>{(taskStatus.progress * 100).toFixed(0)}%</span>
            </div>

            {/* 进度条 */}
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className={`h-3 rounded-full transition-all duration-300 ${
                  taskStatus.status === 'completed' ? 'bg-green-500' :
                  taskStatus.status === 'failed' ? 'bg-red-500' : 'bg-primary-600'
                }`}
                style={{ width: `${taskStatus.progress * 100}%` }}
              />
            </div>

            {/* 详细信息 */}
            {taskStatus.total_slices && (
              <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mt-3">
                <div className="flex items-center space-x-2">
                  <span className="font-medium">视频时长:</span>
                  <span>{taskStatus.video_duration?.toFixed(1) || '-'} 秒</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="font-medium">总片段数:</span>
                  <span>{taskStatus.total_slices || '-'}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="font-medium">已处理(入库):</span>
                  <span className="text-green-600 font-semibold">{taskStatus.processed_slices || 0}</span>
                  <span className="text-gray-400 text-xs">/ {taskStatus.total_slices}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="font-medium">已过滤(无效):</span>
                  <span className="text-amber-500 font-semibold">{taskStatus.filtered_slices || 0}</span>
                </div>
              </div>
            )}

            {/* 细粒度当前动作 */}
            {taskStatus.current_action && taskStatus.status !== 'completed' && (
              <div className="mt-3 p-3 bg-white rounded-lg border border-primary-100 text-sm shadow-sm flex items-center space-x-3 animate-pulse">
                <RefreshCw className="h-4 w-4 text-primary-500 animate-spin" />
                <span className="text-gray-700 font-medium">实时节点:</span>
                <span className="text-primary-600 truncate">{taskStatus.current_action}</span>
              </div>
            )}

            {/* 完成状态 */}
            {taskStatus.status === 'completed' && (
              <div className="mt-2 p-3 bg-green-50 rounded border border-green-200 text-green-700 text-sm">
                ✓ 视频处理完成！共生成 {taskStatus.result?.slice_count || 0} 个可搜索片段
              </div>
            )}

            {/* 失败状态 */}
            {taskStatus.status === 'failed' && (
              <div className="mt-2 p-3 bg-red-50 rounded border border-red-200 text-red-700 text-sm">
                ✗ {taskStatus.message}
              </div>
            )}
          </div>
        )}
      </section>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* 视频列表 */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">已处理视频</h2>

            {videos.length === 0 ? (
              <p className="text-gray-500 text-center py-8">
                暂无已处理的视频
              </p>
            ) : (
              <div className="space-y-3">
                {videos.map((video) => (
                  <div
                    key={video.video_id}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedVideo?.video_id === video.video_id
                        ? 'bg-primary-50 border border-primary-200'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                    onClick={() => setSelectedVideo(video)}
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-medium text-gray-900">
                          {video.video_id}
                        </p>
                        <p className="text-sm text-gray-500">
                          {video.slice_count} 个片段
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Link
                          to={`/video/${video.video_id}/slices`}
                          className="px-3 py-1.5 text-sm bg-primary-100 text-primary-700 rounded hover:bg-primary-200"
                        >
                          查看切片
                        </Link>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(video.video_id)
                          }}
                          className="p-1 text-gray-400 hover:text-red-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 视频播放器 */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">视频预览</h2>

            {selectedVideo ? (
              <div className="space-y-4">
                {/* 视频播放器 */}
                <div className="video-container aspect-video bg-black rounded-lg">
                  <video
                    ref={videoRef}
                    src={`/api/stream/${selectedVideo.video_id}`}
                    className="w-full h-full object-contain"
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={handleLoadedMetadata}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                  />
                </div>

                {/* 播放控制 */}
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => skip(-10)}
                    className="p-2 rounded-lg hover:bg-gray-100"
                  >
                    <SkipBack className="h-5 w-5" />
                  </button>
                  <button
                    onClick={togglePlay}
                    className="p-3 rounded-full bg-primary-600 text-white hover:bg-primary-700"
                  >
                    {isPlaying ? (
                      <Pause className="h-5 w-5" />
                    ) : (
                      <Play className="h-5 w-5" />
                    )}
                  </button>
                  <button
                    onClick={() => skip(10)}
                    className="p-2 rounded-lg hover:bg-gray-100"
                  >
                    <SkipForward className="h-5 w-5" />
                  </button>
                  <span className="text-sm text-gray-500">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>

                {/* 时间轴 */}
                <Timeline
                  duration={duration}
                  currentTime={currentTime}
                  onSeek={seekTo}
                  slices={selectedVideo.slices || []}
                />
              </div>
            ) : (
              <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center text-gray-500">
                选择一个视频进行预览
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default VideoPage
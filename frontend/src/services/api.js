import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 600000, // 增加到 600 秒
})

// 系统配置 API
export const getConfig = async () => {
  const response = await api.get('/config')
  return response.data
}

// 视频相关 API
export const uploadVideo = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/videos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const processVideo = async (videoPath, videoId, customRequiredObjects = null, enableMotionDetection = null, enableObjectDetection = null, motionThreshold = null, smartScanMode = null) => {
  const params = { video_path: videoPath, video_id: videoId }
  if (customRequiredObjects && customRequiredObjects.length > 0) {
    params.custom_required_objects = customRequiredObjects.join(',')
  }
  if (enableMotionDetection !== null) {
    params.enable_motion_detection = enableMotionDetection
  }
  if (enableObjectDetection !== null) {
    params.enable_object_detection = enableObjectDetection
  }
  if (motionThreshold !== null) {
    params.motion_threshold = motionThreshold
  }
  if (smartScanMode !== null) {
    params.smart_scan_mode = smartScanMode
  }
  const response = await api.post('/videos/process', null, { params })
  return response.data
}

export const getTaskStatus = async (taskId) => {
  const response = await api.get(`/videos/tasks/${taskId}`)
  return response.data
}

export const getVideos = async () => {
  const response = await api.get('/videos')
  return response.data
}

export const deleteVideo = async (videoId) => {
  const response = await api.delete(`/videos/${videoId}`)
  return response.data
}

export const getVideoSlices = async (videoId) => {
  const response = await api.get(`/videos/${videoId}/slices`)
  return response.data
}

export const listAllSlices = async (videoId, limit = 100, offset = 0) => {
  const response = await api.get('/slices', {
    params: { video_id: videoId, limit, offset }
  })
  return response.data
}

// 搜索相关 API
export const searchVideos = async (query, options = {}) => {
  const response = await api.post('/search', {
    query,
    video_id: options.videoId,
    top_k: options.topK || 10,
    verify_top_n: options.verifyTopN || 3,
  })
  return response.data
}

export const searchByFeatures = async (features, options = {}) => {
  const response = await api.post('/search/features', {
    features,
    video_id: options.videoId,
    top_k: options.topK || 10,
  })
  return response.data
}

// 分析相关 API
export const analyzeSlice = async (sliceId, focusFeatures) => {
  const response = await api.post('/analyze', {
    slice_id: sliceId,
    focus_features: focusFeatures,
  })
  return response.data
}

export const getSlice = async (sliceId) => {
  const response = await api.get(`/slices/${sliceId}`)
  return response.data
}

// 流媒体 URL
export const getStreamUrl = (videoId, start, end) => {
  let url = `/api/stream/${videoId}`
  const params = new URLSearchParams()
  if (start) params.append('start', start)
  if (end) params.append('end', end)
  if (params.toString()) url += `?${params.toString()}`
  return url
}

// 直接匹配 API (新增功能)
export const directMatch = async (videoPaths, query, options = {}) => {
  const response = await api.post('/direct-match', {
    video_paths: videoPaths,
    query,
    top_k: options.topK || 10,
    store_results: options.storeResults !== false,
  })
  return response.data
}

export const directMatchUpload = async (files, query, options = {}) => {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })

  const params = new URLSearchParams()
  params.append('query', query)
  params.append('top_k', options.topK || 10)
  params.append('store_results', options.storeResults !== false)

  const response = await api.post(`/direct-match/upload?${params.toString()}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const directMatchAsync = async (videoPaths, query, options = {}) => {
  const response = await api.post('/direct-match/async', {
    video_paths: videoPaths,
    query,
    top_k: options.topK || 10,
    store_results: options.storeResults !== false,
  })
  return response.data
}

export default api
import { useState, useEffect } from 'react'
import { searchVideos } from '../services/api'

/**
 * 搜索 Hook
 */
export function useSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const search = async (searchQuery) => {
    if (!searchQuery.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await searchVideos(searchQuery)
      setResults(response.results || [])
    } catch (err) {
      setError(err.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return {
    query,
    setQuery,
    results,
    loading,
    error,
    search,
  }
}

/**
 * 视频播放器 Hook
 */
export function useVideoPlayer(videoRef) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)

  useEffect(() => {
    const video = videoRef?.current
    if (!video) return

    const handleTimeUpdate = () => setCurrentTime(video.currentTime)
    const handleLoadedMetadata = () => setDuration(video.duration)
    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)

    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('loadedmetadata', handleLoadedMetadata)
    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('loadedmetadata', handleLoadedMetadata)
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
    }
  }, [videoRef])

  const togglePlay = () => {
    const video = videoRef?.current
    if (!video) return

    if (isPlaying) {
      video.pause()
    } else {
      video.play()
    }
  }

  const seek = (time) => {
    const video = videoRef?.current
    if (!video) return
    video.currentTime = Math.max(0, Math.min(duration, time))
  }

  const skip = (seconds) => {
    seek(currentTime + seconds)
  }

  const setVolumeLevel = (level) => {
    const video = videoRef?.current
    if (!video) return
    video.volume = level
    setVolume(level)
  }

  return {
    isPlaying,
    currentTime,
    duration,
    volume,
    togglePlay,
    seek,
    skip,
    setVolumeLevel,
  }
}

/**
 * 文件上传 Hook
 */
export function useFileUpload() {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  const upload = async (file, uploadFn) => {
    setUploading(true)
    setProgress(0)
    setError(null)

    try {
      const result = await uploadFn(file, (p) => setProgress(p))
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setUploading(false)
    }
  }

  return {
    uploading,
    progress,
    error,
    upload,
  }
}
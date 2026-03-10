import React, { useState, useEffect } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Search, Upload, Video, Shield, MessageCircle, Loader2, CheckCircle, XCircle, Target } from 'lucide-react'

// 全局任务存储
export const taskStore = {
  tasks: new Map(),
  listeners: [],

  set(taskId, status) {
    this.tasks.set(taskId, status)
    this.notify()
  },

  get(taskId) {
    return this.tasks.get(taskId)
  },

  delete(taskId) {
    this.tasks.delete(taskId)
    this.notify()
  },

  notify() {
    this.listeners.forEach(fn => fn(this.getAll()))
  },

  getAll() {
    return Array.from(this.tasks.entries()).map(([id, status]) => ({ id, ...status }))
  },

  subscribe(fn) {
    this.listeners.push(fn)
    return () => {
      this.listeners = this.listeners.filter(l => l !== fn)
    }
  }
}

function Layout() {
  const location = useLocation()
  const [activeTasks, setActiveTasks] = useState([])

  useEffect(() => {
    return taskStore.subscribe((tasks) => {
      setActiveTasks(tasks.filter(t => t.status === 'processing'))
    })
  }, [])

  const navItems = [
    { path: '/', label: '首页', icon: Shield },
    { path: '/chat', label: '智能检索', icon: MessageCircle },
    { path: '/direct-match', label: '直接匹配', icon: Target },
    { path: '/video', label: '视频管理', icon: Video },
  ]

  return (
    <div className="min-h-screen flex flex-col">
      {/* 头部导航 */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2">
              <Shield className="h-8 w-8 text-primary-600" />
              <span className="text-xl font-bold text-gray-900">猎影</span>
              <span className="text-sm text-gray-500">ShadowHunter</span>
            </Link>

            {/* 导航菜单 */}
            <nav className="flex space-x-8">
              {navItems.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname === item.path
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </div>
      </main>

      {/* 页脚 */}
      <footer className="bg-white border-t">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-gray-500">
            猎影 (ShadowHunter) - 基于智谱 AI 的全栈视频语义检索系统
          </p>
        </div>
      </footer>
    </div>
  )
}

export default Layout
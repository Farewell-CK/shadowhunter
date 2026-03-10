import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Upload, Video, Zap, Eye, Target } from 'lucide-react'

function HomePage() {
  const navigate = useNavigate()

  const features = [
    {
      icon: Zap,
      title: '智能分片',
      description: '8秒黄金窗口，5秒步长重叠分片，确保动作完整性',
    },
    {
      icon: Eye,
      title: '视觉理解',
      description: 'GLM-4.6V 视频分析，精准识别人物、车辆、行为',
    },
    {
      icon: Target,
      title: '语义检索',
      description: '自然语言搜索，秒级定位目标视频片段',
    },
  ]

  return (
    <div className="space-y-12">
      {/* Hero 区域 */}
      <section className="text-center py-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          视频语义检索系统
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          将海量监控视频转化为可语义检索的知识库
          <br />
          告别逐帧查看，实现秒级精准定位
        </p>

        {/* 快速入口 */}
        <div className="flex justify-center space-x-4">
          <button
            onClick={() => navigate('/search')}
            className="flex items-center space-x-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Search className="h-5 w-5" />
            <span>开始搜索</span>
          </button>
          <button
            onClick={() => navigate('/video')}
            className="flex items-center space-x-2 px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <Upload className="h-5 w-5" />
            <span>上传视频</span>
          </button>
        </div>
      </section>

      {/* 功能特点 */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">
          核心能力
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <div
                key={index}
                className="bg-white rounded-xl shadow-sm p-6 hover:shadow-md transition-shadow"
              >
                <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
                  <Icon className="h-6 w-6 text-primary-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600">
                  {feature.description}
                </p>
              </div>
            )
          })}
        </div>
      </section>

      {/* 使用流程 */}
      <section className="bg-white rounded-xl shadow-sm p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">
          使用流程
        </h2>
        <div className="grid md:grid-cols-4 gap-4">
          {[
            { step: 1, title: '上传视频', desc: '支持长视频上传' },
            { step: 2, title: '自动处理', desc: 'AI 智能分片分析' },
            { step: 3, title: '语义搜索', desc: '自然语言描述目标' },
            { step: 4, title: '精准定位', desc: '秒级视频切片回放' },
          ].map((item) => (
            <div key={item.step} className="text-center">
              <div className="w-10 h-10 bg-primary-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 font-bold">
                {item.step}
              </div>
              <h3 className="font-semibold text-gray-900">{item.title}</h3>
              <p className="text-sm text-gray-500">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 搜索示例 */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 mb-6">
          搜索示例
        </h2>
        <div className="bg-gray-100 rounded-lg p-6">
          <p className="text-gray-600 mb-4">试试这些查询语句：</p>
          <div className="flex flex-wrap gap-2">
            {[
              '骑电动车戴白色头盔的人',
              '穿绿色上衣的男子',
              '白色轿车经过路口',
              '手提黑色背包的行人',
            ].map((query) => (
              <button
                key={query}
                onClick={() => navigate(`/search?q=${encodeURIComponent(query)}`)}
                className="px-4 py-2 bg-white rounded-full text-sm text-gray-700 hover:bg-primary-50 hover:text-primary-700 transition-colors"
              >
                {query}
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

export default HomePage
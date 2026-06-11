// Node-type icons mapped to @vicons/ionicons5 components.
// Render via <n-icon :component="..."/> or <n-icon><Comp/></n-icon>.
import {
  GridOutline,          // overview
  DocumentTextOutline,  // requirements
  ColorPaletteOutline,  // design
  LayersOutline,        // stack / external deps
  BrowsersOutline,      // frontend
  HardwareChipOutline,  // backend
  ServerOutline,        // database
  FlaskOutline,         // test
  RocketOutline,        // deploy
  GitBranchOutline,     // decision
  BulbOutline,          // experience
  FolderOutline,        // default
} from '@vicons/ionicons5'

export const NODE_ICON_MAP = {
  '项目概况': GridOutline,
  '项目说明': GridOutline,
  '架构概览': GridOutline,
  '外部依赖': LayersOutline,
  '需求': DocumentTextOutline,
  '原始需求': DocumentTextOutline,
  '需求拆解': DocumentTextOutline,
  '需求变更': DocumentTextOutline,
  '待确认': DocumentTextOutline,
  '设计': ColorPaletteOutline,
  '架构设计': ColorPaletteOutline,
  '接口设计': ColorPaletteOutline,
  '数据模型': ServerOutline,
  '原型设计': ColorPaletteOutline,
  '技术栈': LayersOutline,
  '前端': BrowsersOutline,
  '功能实现': BrowsersOutline,
  '后端': HardwareChipOutline,
  '数据库': ServerOutline,
  '表结构': ServerOutline,
  'SQL优化': ServerOutline,
  '数据迁移': ServerOutline,
  '故障记录': FlaskOutline,
  '测试': FlaskOutline,
  '单元测试': FlaskOutline,
  '集成测试': FlaskOutline,
  '测试技巧': FlaskOutline,
  '缺陷记录': FlaskOutline,
  '部署': RocketOutline,
  '环境配置': RocketOutline,
  'Docker部署': RocketOutline,
  '发布流程': RocketOutline,
  '故障恢复': RocketOutline,
  '决策记录': GitBranchOutline,
  '技术选型': GitBranchOutline,
  '架构决策': GitBranchOutline,
  '历史原因': GitBranchOutline,
  '方案对比': GitBranchOutline,
  '经验库': BulbOutline,
  '开发技巧': BulbOutline,
  '调试技巧': BulbOutline,
  '常见坑': BulbOutline,
  '问题记录': FlaskOutline,
  '优化记录': BulbOutline,
  '开发经验': BulbOutline,
}

export const DEFAULT_NODE_ICON = FolderOutline

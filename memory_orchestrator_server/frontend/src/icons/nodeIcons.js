import IconNodeOverview from './IconNodeOverview.svg'
import IconNodeReqs from './IconNodeReqs.svg'
import IconNodeDesign from './IconNodeDesign.svg'
import IconNodeStack from './IconNodeStack.svg'
import IconNodeFrontend from './IconNodeFrontend.svg'
import IconNodeBackend from './IconNodeBackend.svg'
import IconDatabase from './IconDatabase.svg'
import IconNodeTest from './IconNodeTest.svg'
import IconNodeDeploy from './IconNodeDeploy.svg'
import IconNodeDecision from './IconNodeDecision.svg'
import IconNodeExperience from './IconNodeExperience.svg'
import IconNodeDefault from './IconNodeDefault.svg'

export const NODE_ICON_MAP = {
  '项目概况': IconNodeOverview,
  '项目说明': IconNodeOverview,
  '架构概览': IconNodeOverview,
  '外部依赖': IconNodeStack,
  '需求': IconNodeReqs,
  '原始需求': IconNodeReqs,
  '需求拆解': IconNodeReqs,
  '需求变更': IconNodeReqs,
  '待确认': IconNodeReqs,
  '设计': IconNodeDesign,
  '架构设计': IconNodeDesign,
  '接口设计': IconNodeDesign,
  '数据模型': IconDatabase,
  '原型设计': IconNodeDesign,
  '技术栈': IconNodeStack,
  '前端': IconNodeFrontend,
  '功能实现': IconNodeFrontend,
  '后端': IconNodeBackend,
  '数据库': IconDatabase,
  '表结构': IconDatabase,
  'SQL优化': IconDatabase,
  '数据迁移': IconDatabase,
  '故障记录': IconNodeTest,
  '测试': IconNodeTest,
  '单元测试': IconNodeTest,
  '集成测试': IconNodeTest,
  '测试技巧': IconNodeTest,
  '缺陷记录': IconNodeTest,
  '部署': IconNodeDeploy,
  '环境配置': IconNodeDeploy,
  'Docker部署': IconNodeDeploy,
  '发布流程': IconNodeDeploy,
  '故障恢复': IconNodeDeploy,
  '决策记录': IconNodeDecision,
  '技术选型': IconNodeDecision,
  '架构决策': IconNodeDecision,
  '历史原因': IconNodeDecision,
  '方案对比': IconNodeDecision,
  '经验库': IconNodeExperience,
  '开发技巧': IconNodeExperience,
  '调试技巧': IconNodeExperience,
  '常见坑': IconNodeExperience,
  '问题记录': IconNodeTest,
  '优化记录': IconNodeExperience,
  '开发经验': IconNodeExperience,
}

export const DEFAULT_NODE_ICON = IconNodeDefault

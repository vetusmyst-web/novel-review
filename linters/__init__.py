#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L1 硬性检查插件包
=================
每个模块暴露：
  NAME     : 规则名
  DESC     : 说明
  check(text, ctx) -> list[dict]
            ctx 含 book_cfg / chapter 等上下文
返回的每个 dict 字段：
  type     规则类型（"标点" "分段" "字数" ...）
  desc     问题描述
  severity "高" "中" "低"
  fixable  bool，是否支持自动修复
  payload  修复所需数据（可选）
  suggestion 建议

自动修复由 auto_fix(text, ctx) 提供（可选）：
  auto_fix(text, ctx) -> (new_text, [修复说明])
"""

'use client';

import { useState, useRef, useEffect } from 'react';
import { Sparkles, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ThinkingProcessProps {
  content: string;
  isExpanded?: boolean;
  className?: string;
}

/**
 * 思考过程可折叠组件
 * 参考 Nextra 和 Radix UI 的设计风格
 */
export function ThinkingProcess({
  content,
  isExpanded: defaultExpanded = false,
  className,
}: ThinkingProcessProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [isTyping, setIsTyping] = useState(false);
  const [displayedContent, setDisplayedContent] = useState(content);
  const [copied, setCopied] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 当内容变化时，显示打字效果
  useEffect(() => {
    if (content !== displayedContent) {
      setIsTyping(true);
      setDisplayedContent(content);

      // 打字完成后移除打字状态
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
      }, 100);
    }
  }, [content]);

  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!content || content.trim() === '') {
    return null;
  }

  return (
    <details
      open={isExpanded}
      className={cn(
        'group thinking-process my-3 rounded-lg border border-yellow-200 dark:border-yellow-800/50 bg-yellow-50/50 dark:bg-yellow-900/10 overflow-hidden',
        className
      )}
    >
      <summary
        onClick={(e) => {
          e.preventDefault();
          toggleExpand();
        }}
        className="flex items-center justify-between px-3 py-2 cursor-pointer select-none transition-colors hover:bg-yellow-100/50 dark:hover:bg-yellow-900/20"
      >
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
          <span className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
            AI 思考过程
          </span>
          {isTyping && (
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-bounce" />
              <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-bounce [animation-delay:0.15s]" />
              <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-bounce [animation-delay:0.3s]" />
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-yellow-600 dark:text-yellow-400">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-0" />
          ) : (
            <ChevronRight className="h-4 w-4 transition-transform" />
          )}
        </div>
      </summary>

      <div className="px-3 pb-3">
        <div className="relative">
          {/* 内容区域 */}
          <div
            className={cn(
              'p-3 bg-white/60 dark:bg-black/20 rounded-md text-xs font-mono text-yellow-900/80 dark:text-yellow-100/80 whitespace-pre-wrap leading-relaxed',
              'prose-yellow max-w-none',
              isTyping && 'animate-pulse'
            )}
          >
            {displayedContent}
            {isTyping && (
              <span className="inline-block w-2 h-4 ml-1 bg-yellow-600 animate-pulse" />
            )}
          </div>

          {/* 复制按钮 */}
          <button
            onClick={handleCopy}
            className={cn(
              'absolute top-2 right-2 p-1.5 rounded-md transition-all opacity-0 group-hover:opacity-100',
              'bg-yellow-100/80 dark:bg-yellow-900/40 hover:bg-yellow-200/80 dark:hover:bg-yellow-800/50',
              'text-yellow-700 dark:text-yellow-400'
            )}
            title="复制思考过程"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
        </div>

        {/* 底部信息 */}
        <div className="mt-2 flex items-center justify-between text-xs text-yellow-600/70 dark:text-yellow-400/60">
          <span>{content.length} 字符</span>
          <span>由 AI 自动生成</span>
        </div>
      </div>
    </details>
  );
}

/**
 * 流式思考过程组件（用于流式响应期间）
 */
export function StreamingThinkingProcess({
  content,
  isGenerating,
  className,
}: {
  content: string;
  isGenerating: boolean;
  className?: string;
}) {
  if (!content || content.trim() === '') {
    return null;
  }

  return (
    <div
      className={cn(
        'my-3 rounded-lg border border-yellow-200 dark:border-yellow-800/50',
        'bg-gradient-to-br from-yellow-50/80 to-orange-50/80 dark:from-yellow-900/20 dark:to-orange-900/10',
        'overflow-hidden',
        className
      )}
    >
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2 bg-yellow-100/50 dark:bg-yellow-900/30">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-yellow-600 dark:text-yellow-400 animate-pulse" />
          <span className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
            思考中
          </span>
          {isGenerating && (
            <span className="flex items-center gap-1">
              <span className="w-1 h-1 bg-yellow-600 rounded-full animate-ping" />
              <span className="w-1 h-1 bg-yellow-600 rounded-full animate-ping [animation-delay:0.2s]" />
              <span className="w-1 h-1 bg-yellow-600 rounded-full animate-ping [animation-delay:0.4s]" />
            </span>
          )}
        </div>
      </div>

      {/* 内容 */}
      <div className="p-3">
        <div className="p-3 bg-white/60 dark:bg-black/20 rounded-md text-xs font-mono text-yellow-900/80 dark:text-yellow-100/80 whitespace-pre-wrap leading-relaxed">
          {content}
          {isGenerating && (
            <span className="inline-block w-2 h-4 ml-1 bg-yellow-600 animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}

export default ThinkingProcess;

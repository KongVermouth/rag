'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options?: { value: string | number; label: string }[];
}

export function Select({ className, label, error, options, id, children, ...props }: SelectProps) {
  const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={selectId}
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        className={cn(
          'w-full px-3 py-2 border rounded-lg text-sm transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
          'dark:bg-gray-800 dark:border-gray-600 dark:text-white',
          error ? 'border-red-500 focus:ring-red-500' : 'border-gray-300',
          'disabled:bg-gray-100 disabled:cursor-not-allowed dark:disabled:bg-gray-700',
          className
        )}
        {...props}
      >
        {options ? (
          options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))
        ) : (
          children
        )}
      </select>
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
    </div>
  );
}

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export function Textarea({ className, label, error, id, ...props }: TextareaProps) {
  const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={textareaId}
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          {label}
        </label>
      )}
      <textarea
        id={textareaId}
        className={cn(
          'w-full px-3 py-2 border rounded-lg text-sm transition-colors resize-none',
          'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
          'dark:bg-gray-800 dark:border-gray-600 dark:text-white',
          error ? 'border-red-500 focus:ring-red-500' : 'border-gray-300',
          'disabled:bg-gray-100 disabled:cursor-not-allowed dark:disabled:bg-gray-700',
          className
        )}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
    </div>
  );
}

interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Switch({ className, label, id, ...props }: SwitchProps) {
  const switchId = id || `switch-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className="flex items-center space-x-2">
      <div className="relative inline-flex h-6 w-11 items-center">
        <input
          type="checkbox"
          id={switchId}
          className={cn(
            "peer h-6 w-11 cursor-pointer appearance-none rounded-full bg-gray-200 transition-colors checked:bg-blue-600 dark:bg-gray-700",
            className
          )}
          {...props}
        />
        <span className="pointer-events-none absolute left-1 h-4 w-4 transform rounded-full bg-white transition-transform peer-checked:translate-x-5" />
      </div>
      {label && (
        <label
          htmlFor={switchId}
          className="text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer"
        >
          {label}
        </label>
      )}
    </div>
  );
}

/**
 * Component for displaying database query results with modern table design
 */

import React, { useState, useMemo } from 'react';
import {
  Search,
  Download,
  Copy,
  Clock,
  AlertCircle,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { QueryResult } from '../types/chat.types';
import clsx from 'clsx';

interface QueryResultsProps {
  queryResult: QueryResult;
  className?: string;
}

const QueryResults: React.FC<QueryResultsProps> = ({ 
  queryResult, 
  className = '' 
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [searchTerm, setSearchTerm] = useState('');
  
  const itemsPerPage = 10;

  // Provide safe defaults for data and columns
  const { data = [], columns = [] } = queryResult || { data: [], columns: [] };

  // Filter data based on search term
  const filteredData = useMemo(() => {
    if (!searchTerm) return data;
    
    return data.filter(row =>
      Object.values(row).some(value =>
        String(value).toLowerCase().includes(searchTerm.toLowerCase())
      )
    );
  }, [data, searchTerm]);

  // Sort data
  const sortedData = useMemo(() => {
    if (!sortColumn) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];
      
      // Handle null/undefined values
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sortDirection === 'asc' ? -1 : 1;
      if (bVal == null) return sortDirection === 'asc' ? 1 : -1;
      
      // Convert to strings for comparison
      const aStr = String(aVal);
      const bStr = String(bVal);
      
      // Try numeric comparison first
      const aNum = Number(aStr);
      const bNum = Number(bStr);
      
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortDirection === 'asc' ? aNum - bNum : bNum - aNum;
      }
      
      // String comparison
      return sortDirection === 'asc' 
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr);
    });
  }, [filteredData, sortColumn, sortDirection]);

  // Paginate data
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return sortedData.slice(startIndex, startIndex + itemsPerPage);
  }, [sortedData, currentPage]);

  // Early return if queryResult is null or undefined (after ALL hooks)
  if (!queryResult) {
    return null;
  }

  const totalPages = Math.ceil(sortedData.length / itemsPerPage);

  // Handle empty or error results (after all hooks are defined)
  if (!queryResult.success || !queryResult.data || queryResult.data.length === 0) {
    return (
      <div className="bg-red-400/10 border border-red-400/50 rounded-xl p-3 mt-2">
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-200">
            {queryResult.error || 'No data returned from query'}
          </p>
        </div>
      </div>
    );
  }

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
    setCurrentPage(1); // Reset to first page when sorting
  };

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1); // Reset to first page when searching
  };

  const handlePageChange = (_: React.ChangeEvent<unknown> | null, page: number) => {
    setCurrentPage(page);
  };

  const exportToCSV = () => {
    const csvContent = [
      columns.join(','),
      ...sortedData.map(row => 
        columns.map(col => {
          const value = row[col];
          // Escape quotes and wrap in quotes if contains comma or quotes
          const stringValue = String(value ?? '');
          return stringValue.includes(',') || stringValue.includes('"')
            ? `"${stringValue.replace(/"/g, '""')}"`
            : stringValue;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `query_results_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = async () => {
    try {
      const textContent = [
        columns.join('\t'),
        ...sortedData.map(row => 
          columns.map(col => String(row[col] ?? '')).join('\t')
        )
      ].join('\n');

      await navigator.clipboard.writeText(textContent);
      console.log('Results copied to clipboard');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  return (
    <div className="bg-white mt-4 border border-gray-300 rounded-xl shadow-sm overflow-hidden">
      {/* Header Toolbar */}
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          {/* Results Info */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-primary-500/20 text-primary-300 text-sm font-medium">
              <span>{sortedData.length} rows</span>
            </div>
            {queryResult.execution_time && (
              <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-500/20 text-green-300 text-sm">
                <Clock className="h-3 w-3" />
                <span>{queryResult.execution_time}ms</span>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search results..."
                value={searchTerm}
                onChange={handleSearch}
                className="pl-9 pr-3 py-2 w-48 glass-dark border-gray-600/50 rounded-lg text-sm text-gray-100 placeholder-gray-400 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              />
            </div>

            {/* Copy Button */}
            <button
              onClick={copyToClipboard}
              title="Copy to clipboard"
              className="p-2 rounded-lg glass-dark hover:bg-white/20 text-gray-400 hover:text-white transition-colors"
            >
              <Copy className="h-4 w-4" />
            </button>

            {/* Export Button */}
            <button
              onClick={exportToCSV}
              className="flex items-center gap-2 px-3 py-2 btn-secondary text-sm"
            >
              <Download className="h-4 w-4" />
              CSV
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-auto max-h-96 scrollbar-thin">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-100 backdrop-blur-sm">
            <tr className="border-b border-gray-200">
              {columns.map(column => (
                <th
                  key={column}
                  className="text-left px-4 py-3 font-semibold text-gray-700">
                >
                  <button
                    onClick={() => handleSort(column)}
                    className="flex items-center gap-1 hover:text-white transition-colors group"
                  >
                    <span>{column}</span>
                    <div className="flex flex-col">
                      {sortColumn === column ? (
                        sortDirection === 'asc' ? (
                          <ChevronUp className="h-3 w-3 text-primary-400" />
                        ) : (
                          <ChevronDown className="h-3 w-3 text-primary-400" />
                        )
                      ) : (
                        <div className="h-3 w-3 opacity-0 group-hover:opacity-50 transition-opacity">
                          <ChevronUp className="h-3 w-3 absolute" />
                          <ChevronDown className="h-3 w-3 absolute" />
                        </div>
                      )}
                    </div>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, index) => (
              <tr 
                key={index}
                className={clsx(
                  'border-b border-gray-100 hover:bg-gray-50 transition-colors',
                  index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                )}
              >
                {columns.map(column => (
                  <td 
                    key={column}
                    className="px-4 py-3 max-w-xs overflow-hidden text-ellipsis whitespace-nowrap text-gray-900">
                    title={String(row[column] ?? '')}
                  >
                    {row[column] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="bg-gray-50 border-t border-gray-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Showing {(currentPage - 1) * itemsPerPage + 1}-{Math.min(currentPage * itemsPerPage, sortedData.length)} of {sortedData.length} rows
            </p>
            
            <div className="flex items-center gap-1">
              {/* First Page */}
              <button
                onClick={() => handlePageChange(null, 1)}
                disabled={currentPage === 1}
                className={clsx(
                  'p-2 rounded-lg transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'enabled:hover:bg-gray-100 text-gray-500 enabled:hover:text-gray-700'
                )}
              >
                <ChevronsLeft className="h-4 w-4" />
              </button>
              
              {/* Previous Page */}
              <button
                onClick={() => handlePageChange(null, currentPage - 1)}
                disabled={currentPage === 1}
                className={clsx(
                  'p-2 rounded-lg transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'enabled:hover:bg-gray-100 text-gray-500 enabled:hover:text-gray-700'
                )}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              
              {/* Page Numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(page => {
                    return Math.abs(page - currentPage) <= 2 || page === 1 || page === totalPages;
                  })
                  .map((page, index, array) => {
                    const showEllipsis = index > 0 && page - array[index - 1] > 1;
                    return (
                      <React.Fragment key={page}>
                        {showEllipsis && (
                          <span className="px-2 text-gray-500">...</span>
                        )}
                        <button
                          onClick={() => handlePageChange(null, page)}
                          className={clsx(
                            'px-3 py-1 rounded-lg text-sm transition-colors',
                            page === currentPage
                              ? 'bg-primary-600 text-white'
                              : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                          )}
                        >
                          {page}
                        </button>
                      </React.Fragment>
                    );
                  })}
              </div>
              
              {/* Next Page */}
              <button
                onClick={() => handlePageChange(null, currentPage + 1)}
                disabled={currentPage === totalPages}
                className={clsx(
                  'p-2 rounded-lg transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'enabled:hover:bg-gray-100 text-gray-500 enabled:hover:text-gray-700'
                )}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              
              {/* Last Page */}
              <button
                onClick={() => handlePageChange(null, totalPages)}
                disabled={currentPage === totalPages}
                className={clsx(
                  'p-2 rounded-lg transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'enabled:hover:bg-gray-100 text-gray-500 enabled:hover:text-gray-700'
                )}
              >
                <ChevronsRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryResults;
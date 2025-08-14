/**
 * Component for displaying database query results in a table format
 */

import React, { useState, useMemo } from 'react';
import { QueryResult } from '../types/chat.types';

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

  const { data = [], columns = [] } = queryResult;

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

  const totalPages = Math.ceil(sortedData.length / itemsPerPage);

  // Handle empty or error results (after all hooks are defined)
  if (!queryResult.success || !queryResult.data || queryResult.data.length === 0) {
    return (
      <div className={`query-results error ${className}`}>
        <div className="error-message">
          {queryResult.error || 'No data returned from query'}
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

  const handlePageChange = (page: number) => {
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
      // You might want to show a toast notification here
      console.log('Results copied to clipboard');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  return (
    <div className={`query-results ${className}`}>
      {/* Header with search and actions */}
      <div className="results-header">
        <div className="results-info">
          <span className="results-count">
            {sortedData.length} of {data.length} rows
            {queryResult.execution_time && (
              <span className="execution-time">
                ({queryResult.execution_time}ms)
              </span>
            )}
          </span>
        </div>
        
        <div className="results-actions">
          <input
            type="text"
            placeholder="Search results..."
            value={searchTerm}
            onChange={handleSearch}
            className="search-input"
          />
          <button onClick={copyToClipboard} className="action-button">
            Copy
          </button>
          <button onClick={exportToCSV} className="action-button">
            Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="table-container">
        <table className="results-table">
          <thead>
            <tr>
              {columns.map(column => (
                <th 
                  key={column}
                  onClick={() => handleSort(column)}
                  className={`sortable ${sortColumn === column ? `sorted-${sortDirection}` : ''}`}
                >
                  {column}
                  <span className="sort-indicator">
                    {sortColumn === column 
                      ? (sortDirection === 'asc' ? ' ↑' : ' ↓')
                      : ' ↕'
                    }
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, index) => (
              <tr key={index}>
                {columns.map(column => (
                  <td key={column} title={String(row[column] ?? '')}>
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
        <div className="pagination">
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="page-button"
          >
            Previous
          </button>
          
          <span className="page-info">
            Page {currentPage} of {totalPages}
          </span>
          
          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="page-button"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default QueryResults;
/**
 * Component for displaying database query results using Material UI
 */

import React, { useState, useMemo } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Button,
  Typography,
  IconButton,
  Pagination,
  Chip,
  Alert,
  Toolbar,
  InputAdornment,
} from '@mui/material';
import {
  Search as SearchIcon,
  Download as DownloadIcon,
  ContentCopy as CopyIcon,
  Schedule as TimeIcon,
} from '@mui/icons-material';
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
      <Alert severity="error" sx={{ mt: 1 }}>
        {queryResult.error || 'No data returned from query'}
      </Alert>
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

  const handlePageChange = (_: React.ChangeEvent<unknown>, page: number) => {
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
    <Paper 
      variant="outlined" 
      sx={{ 
        mt: 2,
        overflow: 'hidden',
        border: 1,
        borderColor: 'divider',
      }}
    >
      {/* Header Toolbar */}
      <Toolbar
        variant="dense"
        sx={{
          bgcolor: 'background.default',
          borderBottom: 1,
          borderColor: 'divider',
          px: 2,
          py: 1,
        }}
      >
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Results Info */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              label={`${sortedData.length} rows`}
              size="small"
              color="primary"
              variant="outlined"
            />
            {queryResult.execution_time && (
              <Chip
                icon={<TimeIcon />}
                label={`${queryResult.execution_time}ms`}
                size="small"
                color="success"
                variant="outlined"
              />
            )}
          </Box>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {/* Search */}
          <TextField
            size="small"
            placeholder="Search results..."
            value={searchTerm}
            onChange={handleSearch}
            sx={{ width: 200 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />

          {/* Copy Button */}
          <IconButton
            size="small"
            onClick={copyToClipboard}
            title="Copy to clipboard"
          >
            <CopyIcon fontSize="small" />
          </IconButton>

          {/* Export Button */}
          <Button
            size="small"
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={exportToCSV}
          >
            CSV
          </Button>
        </Box>
      </Toolbar>

      {/* Table */}
      <TableContainer sx={{ maxHeight: 400 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              {columns.map(column => (
                <TableCell
                  key={column}
                  sortDirection={sortColumn === column ? sortDirection : false}
                >
                  <TableSortLabel
                    active={sortColumn === column}
                    direction={sortColumn === column ? sortDirection : 'asc'}
                    onClick={() => handleSort(column)}
                    sx={{ fontWeight: 600 }}
                  >
                    {column}
                  </TableSortLabel>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedData.map((row, index) => (
              <TableRow 
                key={index}
                hover
                sx={{ '&:nth-of-type(odd)': { bgcolor: 'action.hover' } }}
              >
                {columns.map(column => (
                  <TableCell 
                    key={column}
                    sx={{
                      maxWidth: 200,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={String(row[column] ?? '')}
                  >
                    {row[column] ?? ''}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            p: 2,
            borderTop: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
          }}
        >
          <Pagination
            count={totalPages}
            page={currentPage}
            onChange={handlePageChange}
            color="primary"
            size="small"
            showFirstButton
            showLastButton
          />
          <Typography variant="caption" color="text.secondary" sx={{ ml: 2 }}>
            Showing {(currentPage - 1) * itemsPerPage + 1}-{Math.min(currentPage * itemsPerPage, sortedData.length)} of {sortedData.length} rows
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default QueryResults;
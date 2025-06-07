import React, { useState } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const ParseFile = () => {
  const [file, setFile] = useState(null);
  const [loadingMethod, setLoadingMethod] = useState('auto');
  const [parsingOption, setParsingOption] = useState('all_text');
  const [parsedContent, setParsedContent] = useState(null);
  const [status, setStatus] = useState('');
  const [docName, setDocName] = useState('');
  const [isProcessed, setIsProcessed] = useState(false);
  const [fileType, setFileType] = useState('pdf');
  const [isLoading, setIsLoading] = useState(false);

  const handleProcess = async () => {
    if (!file || !loadingMethod || !parsingOption) {
      setStatus('Please select all required options');
      return;
    }

    setStatus('Processing...');
    setParsedContent(null);
    setIsProcessed(false);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('loading_method', loadingMethod);
      formData.append('parsing_option', parsingOption);
      formData.append('file_type', fileType);

      const response = await fetch(`${apiBaseUrl}/parse`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setParsedContent(data.parsed_content);
      setStatus('Processing completed successfully!');
      setIsProcessed(true);
    } catch (error) {
      console.error('Error:', error);
      setStatus(`Error: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      const fileName = selectedFile.name;
      setDocName(fileName.replace(/\.[^/.]+$/, "")); // 移除扩展名
      
      // 根据文件扩展名设置文件类型和默认加载方法
      const fileExtension = fileName.split('.').pop().toLowerCase();
      if (fileExtension === 'md') {
        setFileType('markdown');
        // 重置为自动选择加载方法
        setLoadingMethod('auto');
      } else if (fileExtension === 'pdf') {
        setFileType('pdf');
        // 重置为自动选择加载方法
        setLoadingMethod('auto');
      }
    }
  };

  // 根据文件类型获取可用的加载方法
  const getLoadingMethods = () => {
    const commonOptions = [
      { value: 'auto', label: 'Auto (Recommended)' }
    ];
    
    if (fileType === 'markdown') {
      return [
        ...commonOptions,
        { value: 'plain', label: 'Plain Text' },
        { value: 'unstructured', label: 'Unstructured (Structured Parsing)' }
      ];
    } else {
      return [
        ...commonOptions,
        { value: 'pymupdf', label: 'PyMuPDF (Fast)' },
        { value: 'pypdf', label: 'PyPDF (Basic)' },
        { value: 'unstructured', label: 'Unstructured (Structured Parsing)' },
        { value: 'pdfplumber', label: 'PDF Plumber (Table Support)' }
      ];
    }
  };

  // 获取当前加载方法的描述
  const getLoadingMethodDescription = (method) => {
    if (method === 'auto') {
      if (fileType === 'markdown') {
        return 'Automatically selects the best loading method for Markdown (defaults to Unstructured)';
      } else {
        return 'Automatically selects the best loading method for PDF (defaults to PyMuPDF)';
      }
    }
    return '';
  };

  // 获取解析选项的描述
  const getParsingOptionDescription = (option) => {
    const descriptions = {
      'all_text': 'Extract all text content as a continuous flow',
      'by_pages': 'Parse document page by page, preserving page boundaries',
      'by_titles': 'Parse document by identifying titles and organizing content into sections',
      'text_and_tables': 'Separate text and table content',
      'full_parse': 'Full parsing (text + tables + images)'
    };
    return descriptions[option] || '';
  };

  const renderContentItem = (item, idx) => {
    switch (item.type.toLowerCase()) {
      case 'table':
        return (
          <div key={idx} className="p-3 border rounded bg-gray-50 mb-3">
            <div className="font-medium text-sm text-gray-500 mb-1">
              Table - Page {item.page} {item.table_index && `(#${item.table_index})`}
            </div>
            <div className="text-sm overflow-x-auto">
              <pre className="whitespace-pre-wrap bg-white p-2 border rounded">{item.content}</pre>
            </div>
          </div>
        );
      case 'image':
        return (
          <div key={idx} className="p-3 border rounded bg-gray-50 mb-3">
            <div className="font-medium text-sm text-gray-500 mb-1">
              Image Content - Page {item.page} {item.image_index && `(#${item.image_index})`}
              {item.image_alt && <span className="ml-2 text-xs">({item.image_alt})</span>}
            </div>
            <div className="text-sm text-gray-600 bg-white p-2 border rounded">
              {item.content}
            </div>
          </div>
        );
      case 'text':
      case 'title':
      case 'narrative text':
      case 'page':
      default:
        return (
          <div key={idx} className="p-3 border rounded bg-gray-50 mb-3">
            <div className="font-medium text-sm text-gray-500 mb-1">
              {item.type} - Page {item.page}
            </div>
            {item.title && (
              <div className="font-bold text-gray-700 mb-2">
                {item.title}
              </div>
            )}
            <div className="text-sm text-gray-600">
              {item.content}
            </div>
          </div>
        );
    }
  };

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Parse File</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel (3/12) */}
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div>
              <label className="block text-sm font-medium mb-1">Upload File</label>
              <input
                type="file"
                accept=".pdf,.md"
                onChange={handleFileSelect}
                className="block w-full border rounded px-3 py-2"
                required
              />
              <div className="mt-1 text-xs text-gray-500">
                Supported formats: PDF, Markdown (.md)
              </div>
            </div>

            {file && (
              <div className="mt-4 p-3 border rounded bg-gray-50">
                <h4 className="font-medium text-sm mb-2">Selected File</h4>
                <div className="text-xs text-gray-600">
                  <p>Filename: {file.name}</p>
                  <p>Type: {fileType === 'markdown' ? 'Markdown' : 'PDF'}</p>
                  <p>Size: {(file.size / 1024).toFixed(2)} KB</p>
                </div>
              </div>
            )}

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Loading Tool</label>
              <select
                value={loadingMethod}
                onChange={(e) => setLoadingMethod(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                {getLoadingMethods().map(method => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
              <div className="mt-1 text-xs text-gray-500">
                {loadingMethod === 'auto' ? 
                  getLoadingMethodDescription('auto') : 
                  (fileType === 'markdown' ? 
                    'Select loading method suitable for Markdown documents' : 
                    'Select loading method suitable for PDF documents')}
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Parsing Option</label>
              <select
                value={parsingOption}
                onChange={(e) => setParsingOption(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="all_text">All Text</option>
                <option value="by_pages">By Pages</option>
                <option value="by_titles">By Titles</option>
                <option value="text_and_tables">Text and Tables</option>
                <option value="full_parse">Full Parse (Text+Tables+Images)</option>
              </select>
              <div className="mt-1 text-xs text-gray-500">
                {getParsingOptionDescription(parsingOption)}
              </div>
            </div>

            <button 
              onClick={handleProcess}
              className={`mt-4 w-full px-4 py-2 text-white rounded ${
                !file || isLoading
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-blue-500 hover:bg-blue-600'
              }`}
              disabled={!file || isLoading}
            >
              {isLoading ? 'Processing...' : 'Parse File'}
            </button>
          </div>
        </div>

        {/* Right Panel (9/12) */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {parsedContent ? (
            <div className="p-4">
              <h3 className="text-xl font-semibold mb-4">Parsing Results</h3>
              <div className="mb-4 p-3 border rounded bg-gray-100">
                <h4 className="font-medium mb-2">Document Information</h4>
                <div className="text-sm text-gray-600">
                  <p>Filename: {parsedContent.metadata?.filename}</p>
                  <p>Total Pages: {parsedContent.metadata?.total_pages}</p>
                  <p>Parsing Method: {parsedContent.metadata?.parsing_method}</p>
                  <p>File Type: {parsedContent.metadata?.file_type === 'markdown' ? 'Markdown' : 'PDF'}</p>
                  <p>Loading Method: {parsedContent.metadata?.loading_method}</p>
                  <p>Timestamp: {parsedContent.metadata?.timestamp && new Date(parsedContent.metadata.timestamp).toLocaleString()}</p>
                </div>
              </div>
              <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
                {parsedContent.content.map((item, idx) => renderContentItem(item, idx))}
              </div>
            </div>
          ) : (
            <RandomImage message="Upload and parse a file to see the results here" />
          )}
        </div>
      </div>
      
      {status && (
        <div className={`mt-4 p-4 rounded-lg ${
          status.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
        }`}>
          {status}
        </div>
      )}
    </div>
  );
};

export default ParseFile; 
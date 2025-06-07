from datetime import datetime
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownTextSplitter

logger = logging.getLogger(__name__)

class ChunkingService:
    """
    文本分块服务，提供多种文本分块策略
    
    该服务支持以下分块方法：
    - by_pages: 按页面分块，每页作为一个块
    - fixed_size: 按固定大小分块
    - by_paragraphs: 按段落分块
    - by_sentences: 按句子分块
    
    支持的文档类型：
    - PDF: 支持所有分块方法
    - Markdown: 支持所有分块方法，对于 by_paragraphs 方法有特殊处理
    """
    
    def chunk_text(self, text: str, method: str, metadata: dict, page_map: list = None, chunk_size: int = 1000) -> dict:
        """
        将文本按指定方法分块
        
        Args:
            text: 原始文本内容
            method: 分块方法，支持 'by_pages', 'fixed_size', 'by_paragraphs', 'by_sentences'
            metadata: 文档元数据
            page_map: 页面映射列表，每个元素包含页码和页面文本
            chunk_size: 固定大小分块时的块大小
            
        Returns:
            包含分块结果的文档数据结构
        
        Raises:
            ValueError: 当分块方法不支持或页面映射为空时
        """
        try:
            if not page_map:
                raise ValueError("Page map is required for chunking.")
            
            chunks = []
            total_pages = len(page_map)
            
            # 检测文档类型
            filename = metadata.get("filename", "")
            file_type = "markdown" if filename.lower().endswith('.md') else "pdf"
            
            if method == "by_pages":
                # 直接使用 page_map 中的每页作为一个 chunk
                for page_data in page_map:
                    chunk_metadata = {
                        "chunk_id": len(chunks) + 1,
                        "page_number": page_data['page'],
                        "page_range": str(page_data['page']),
                        "word_count": len(page_data['text'].split())
                    }
                    chunks.append({
                        "content": page_data['text'],
                        "metadata": chunk_metadata
                    })
            
            elif method == "fixed_size":
                # 对每页内容进行固定大小分块
                for page_data in page_map:
                    page_chunks = self._fixed_size_chunks(page_data['text'], chunk_size)
                    for idx, chunk in enumerate(page_chunks, 1):
                        chunk_metadata = {
                            "chunk_id": len(chunks) + 1,
                            "page_number": page_data['page'],
                            "page_range": str(page_data['page']),
                            "word_count": len(chunk["text"].split())
                        }
                        chunks.append({
                            "content": chunk["text"],
                            "metadata": chunk_metadata
                        })
            
            elif method == "by_paragraphs":
                # 对每页内容进行段落分块，对 Markdown 文件使用特殊处理
                for page_data in page_map:
                    if file_type == "markdown":
                        page_chunks = self._markdown_paragraph_chunks(page_data['text'])
                    else:
                        page_chunks = self._paragraph_chunks(page_data['text'])
                        
                    for chunk in page_chunks:
                        if chunk["text"].strip():  # 跳过空段落
                            chunk_metadata = {
                                "chunk_id": len(chunks) + 1,
                                "page_number": page_data['page'],
                                "page_range": str(page_data['page']),
                                "word_count": len(chunk["text"].split())
                            }
                            chunks.append({
                                "content": chunk["text"],
                                "metadata": chunk_metadata
                            })
            
            elif method == "by_sentences":
                # 对每页内容进行句子分块
                for page_data in page_map:
                    # 根据文件类型选择不同的分块方法
                    if file_type == "markdown":
                        page_chunks = self._markdown_sentence_chunks(page_data['text'])
                    else:
                        page_chunks = self._sentence_chunks(page_data['text'])
                        
                    for chunk in page_chunks:
                        if chunk["text"].strip():  # 跳过空句子
                            chunk_metadata = {
                                "chunk_id": len(chunks) + 1,
                                "page_number": page_data['page'],
                                "page_range": str(page_data['page']),
                                "word_count": len(chunk["text"].split())
                            }
                            chunks.append({
                                "content": chunk["text"],
                                "metadata": chunk_metadata
                            })
            else:
                raise ValueError(f"Unsupported chunking method: {method}")

            # 创建标准化的文档数据结构
            document_data = {
                "filename": metadata.get("filename", ""),
                "total_chunks": len(chunks),
                "total_pages": total_pages,
                "loading_method": metadata.get("loading_method", ""),
                "chunking_method": method,
                "file_type": file_type,
                "chunk_size": chunk_size if method == "fixed_size" else None,
                "timestamp": datetime.now().isoformat(),
                "chunks": chunks
            }
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in chunk_text: {str(e)}")
            raise

    def _fixed_size_chunks(self, text: str, chunk_size: int) -> list[dict]:
        """
        将文本按固定大小分块
        
        Args:
            text: 要分块的文本
            chunk_size: 每块的最大字符数
            
        Returns:
            分块后的文本列表
        """
        if not text.strip():
            return []
            
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=min(200, int(chunk_size * 0.1)),  # 10% 重叠，最大 200 字符
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        texts = splitter.split_text(text)
        return [{"text": t} for t in texts]

    def _paragraph_chunks(self, text: str) -> list[dict]:
        """
        将文本按段落分块
        
        Args:
            text: 要分块的文本
            
        Returns:
            分块后的段落列表
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return [{"text": para} for para in paragraphs]
        
    def _markdown_paragraph_chunks(self, text: str) -> list[dict]:
        """
        将 Markdown 文本按段落和标题分块
        
        Args:
            text: 要分块的 Markdown 文本
            
        Returns:
            分块后的段落列表
        """
        splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=0)
        texts = splitter.split_text(text)
        return [{"text": t} for t in texts]

    def _sentence_chunks(self, text: str) -> list[dict]:
        """
        将文本按句子分块
        
        Args:
            text: 要分块的文本
            
        Returns:
            分块后的句子列表
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=0,
            separators=[".", "!", "?", "\n", " "]
        )
        texts = splitter.split_text(text)
        return [{"text": t} for t in texts]
        
    def _markdown_sentence_chunks(self, text: str) -> list[dict]:
        """
        将 Markdown 文本按句子分块，保留标题结构
        
        Args:
            text: 要分块的 Markdown 文本
            
        Returns:
            分块后的句子列表
        """
        # 首先按 Markdown 结构分块
        md_splitter = MarkdownTextSplitter(chunk_size=2000, chunk_overlap=0)
        md_chunks = md_splitter.split_text(text)
        
        # 然后对每个 Markdown 块进一步按句子分块
        sentence_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=0,
            separators=[".", "!", "?", "\n", " "]
        )
        
        result = []
        for md_chunk in md_chunks:
            sentences = sentence_splitter.split_text(md_chunk)
            for sentence in sentences:
                if sentence.strip():
                    result.append({"text": sentence})
        
        return result

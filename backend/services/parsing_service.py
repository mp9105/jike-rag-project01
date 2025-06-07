import logging
from typing import Dict, List, Optional, Tuple
import fitz  # PyMuPDF
import pandas as pd
from datetime import datetime
import os
import io
import base64
from PIL import Image
import pytesseract
import markdown
from bs4 import BeautifulSoup
import numpy as np
import re
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from unstructured.partition.md import partition_md
from unstructured.partition.pdf import partition_pdf
import cv2

logger = logging.getLogger(__name__)

class ParsingService:
    """
    文档解析服务类
    
    该类提供多种解析策略来提取和构建文档内容，包括：
    - 全文提取
    - 逐页解析
    - 基于标题的分段
    - 文本和表格混合解析
    - 图片内容提取
    - Markdown 文档解析
    
    支持的文档类型：
    - PDF: 支持表格提取、图片识别和文本解析
    - Markdown: 支持表格解析和图片引用识别
    """

    def parse_document(self, file_path: str, text: str, method: str, metadata: dict, page_map: list = None) -> dict:
        """
        使用指定方法解析文档

        参数:
            file_path (str): 文档的文件路径
            text (str): 文档的文本内容
            method (str): 解析方法 ('all_text', 'by_pages', 'by_titles', 'text_and_tables', 'full_parse')
            metadata (dict): 文档元数据，包括文件名和其他属性
            page_map (list): 包含每页内容和元数据的字典列表

        返回:
            dict: 解析后的文档数据，包括元数据和结构化内容

        异常:
            ValueError: 当page_map为空或指定了不支持的解析方法时抛出
        """
        try:
            if not page_map:
                raise ValueError("Page map is required for parsing.")
            
            parsed_content = []
            total_pages = len(page_map)
            
            # 检测文件类型
            filename = metadata.get("filename", "")
            file_type = "markdown" if filename.lower().endswith('.md') else "pdf"
            
            if method == "all_text":
                parsed_content = self._parse_all_text(page_map)
            elif method == "by_pages":
                parsed_content = self._parse_by_pages(page_map)
            elif method == "by_titles":
                parsed_content = self._parse_by_titles(page_map)
            elif method == "text_and_tables":
                if file_type == "pdf":
                    parsed_content = self._parse_pdf_text_and_tables(file_path, page_map)
                else:
                    parsed_content = self._parse_markdown_text_and_tables(text, page_map)
            elif method == "full_parse":
                if file_type == "pdf":
                    parsed_content = self._parse_pdf_full(file_path, page_map)
                else:
                    parsed_content = self._parse_markdown_full(text, file_path, page_map)
            else:
                raise ValueError(f"Unsupported parsing method: {method}")
                
            # Create document-level metadata
            document_data = {
                "metadata": {
                    "filename": metadata.get("filename", ""),
                    "total_pages": total_pages,
                    "parsing_method": method,
                    "file_type": file_type,
                    "timestamp": datetime.now().isoformat()
                },
                "content": parsed_content
            }
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in parse_document: {str(e)}")
            raise

    # 为了向后兼容，保留 parse_pdf 方法
    def parse_pdf(self, text: str, method: str, metadata: dict, page_map: list = None) -> dict:
        """
        使用指定方法解析PDF文档（为向后兼容保留）

        参数:
            text (str): PDF文档的文本内容
            method (str): 解析方法 ('all_text', 'by_pages', 'by_titles', 或 'text_and_tables')
            metadata (dict): 文档元数据，包括文件名和其他属性
            page_map (list): 包含每页内容和元数据的字典列表

        返回:
            dict: 解析后的文档数据，包括元数据和结构化内容

        异常:
            ValueError: 当page_map为空或指定了不支持的解析方法时抛出
        """
        # 由于没有文件路径，这里只能处理文本内容
        return self.parse_document("", text, method, metadata, page_map)

    def _parse_all_text(self, page_map: list) -> list:
        """
        将文档中的所有文本内容提取为连续流

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的文本内容的字典列表
        """
        return [{
            "type": "Text",
            "content": page["text"],
            "page": page["page"]
        } for page in page_map]

    def _parse_by_pages(self, page_map: list) -> list:
        """
        逐页解析文档，保持页面边界

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的分页内容的字典列表
        """
        parsed_content = []
        for page in page_map:
            parsed_content.append({
                "type": "Page",
                "page": page["page"],
                "content": page["text"]
            })
        return parsed_content

    def _parse_by_titles(self, page_map: list) -> list:
        """
        通过识别标题来解析文档并将内容组织成章节

        使用简单的启发式方法识别标题：
        长度小于60个字符且全部大写的行被视为章节标题

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带标题和页码的分章节内容的字典列表
        """
        parsed_content = []
        current_title = None
        current_content = []
        current_page = 1

        for page in page_map:
            lines = page["text"].split('\n')
            for line in lines:
                # Simple heuristic: consider lines with less than 60 chars and all caps as titles
                if len(line.strip()) < 60 and line.isupper():
                    if current_title:
                        parsed_content.append({
                            "type": "section",
                            "title": current_title,
                            "content": '\n'.join(current_content),
                            "page": current_page
                        })
                    current_title = line.strip()
                    current_content = []
                    current_page = page["page"]
                else:
                    current_content.append(line)

        # Add the last section
        if current_title:
            parsed_content.append({
                "type": "section",
                "title": current_title,
                "content": '\n'.join(current_content),
                "page": current_page
            })

        return parsed_content

    def _parse_pdf_text_and_tables(self, file_path: str, page_map: list) -> list:
        """
        解析PDF文档中的文本和表格

        参数:
            file_path (str): PDF文件路径
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含分离的文本和表格内容（带页码）的字典列表
        """
        parsed_content = []
        
        try:
            # 使用PyMuPDF提取表格
            doc = fitz.open(file_path)
            
            for page_data in page_map:
                page_num = page_data["page"]
                page = doc[page_num - 1]  # PyMuPDF页码从0开始
                
                # 提取文本内容（排除表格区域）
                text_content = page_data["text"]
                
                # 提取表格
                tables = page.find_tables()
                if tables and tables.tables:
                    for table_idx, table in enumerate(tables.tables):
                        rows = []
                        for row_idx in range(table.row_count):
                            row_data = []
                            for col_idx in range(table.col_count):
                                cell = table.cells[row_idx * table.col_count + col_idx]
                                if cell:
                                    cell_text = page.get_text("text", cell)
                                    row_data.append(cell_text.strip())
                                else:
                                    row_data.append("")
                            rows.append(row_data)
                        
                        # 转换为Markdown表格格式
                        md_table = self._convert_to_markdown_table(rows)
                        
                        parsed_content.append({
                            "type": "table",
                            "content": md_table,
                            "page": page_num,
                            "table_index": table_idx + 1
                        })
                
                # 添加文本内容
                parsed_content.append({
                    "type": "text",
                    "content": text_content,
                    "page": page_num
                })
            
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting tables from PDF: {str(e)}")
            # 如果表格提取失败，回退到基本文本解析
            for page_data in page_map:
                parsed_content.append({
                    "type": "text",
                    "content": page_data["text"],
                    "page": page_data["page"]
                })
        
        return parsed_content

    def _parse_markdown_text_and_tables(self, text: str, page_map: list) -> list:
        """
        解析Markdown文档中的文本和表格

        参数:
            text (str): Markdown文本内容
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含分离的文本和表格内容的字典列表
        """
        parsed_content = []
        
        try:
            # 将Markdown转换为HTML
            html = markdown.markdown(text, extensions=['tables'])
            soup = BeautifulSoup(html, 'html.parser')
            
            # 提取表格
            tables = soup.find_all('table')
            
            # 如果找到表格，将它们单独解析
            if tables:
                for table_idx, table in enumerate(tables):
                    # 确定表格在哪一页
                    table_text = table.get_text()
                    table_page = 1
                    for page_data in page_map:
                        if table_text in page_data["text"]:
                            table_page = page_data["page"]
                            break
                    
                    # 转换HTML表格为Markdown表格
                    md_table = self._html_table_to_markdown(table)
                    
                    parsed_content.append({
                        "type": "table",
                        "content": md_table,
                        "page": table_page,
                        "table_index": table_idx + 1
                    })
                
                # 添加非表格文本内容
                for page_data in page_map:
                    # 从页面文本中排除表格内容
                    page_text = page_data["text"]
                    for table in tables:
                        table_text = table.get_text()
                        page_text = page_text.replace(table_text, "")
                    
                    if page_text.strip():
                        parsed_content.append({
                            "type": "text",
                            "content": page_text.strip(),
                            "page": page_data["page"]
                        })
            else:
                # 如果没有表格，直接使用页面文本
                for page_data in page_map:
                    parsed_content.append({
                        "type": "text",
                        "content": page_data["text"],
                        "page": page_data["page"]
                    })
        except Exception as e:
            logger.error(f"Error parsing Markdown tables: {str(e)}")
            # 如果表格解析失败，回退到基本文本解析
            for page_data in page_map:
                parsed_content.append({
                    "type": "text",
                    "content": page_data["text"],
                    "page": page_data["page"]
                })
        
        return parsed_content

    def _parse_pdf_full(self, file_path: str, page_map: list) -> list:
        """
        全面解析PDF文档，提取文本、表格和图片

        参数:
            file_path (str): PDF文件路径
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含文本、表格和图片内容的字典列表
        """
        parsed_content = []
        
        try:
            # 使用PyMuPDF提取文本、表格和图片
            doc = fitz.open(file_path)
            
            for page_data in page_map:
                page_num = page_data["page"]
                page = doc[page_num - 1]  # PyMuPDF页码从0开始
                
                # 1. 提取表格
                tables = page.find_tables()
                if tables and tables.tables:
                    for table_idx, table in enumerate(tables.tables):
                        rows = []
                        for row_idx in range(table.row_count):
                            row_data = []
                            for col_idx in range(table.col_count):
                                cell = table.cells[row_idx * table.col_count + col_idx]
                                if cell:
                                    cell_text = page.get_text("text", cell)
                                    row_data.append(cell_text.strip())
                                else:
                                    row_data.append("")
                            rows.append(row_data)
                        
                        # 转换为Markdown表格格式
                        md_table = self._convert_to_markdown_table(rows)
                        
                        parsed_content.append({
                            "type": "table",
                            "content": md_table,
                            "page": page_num,
                            "table_index": table_idx + 1
                        })
                
                # 2. 提取图片
                image_list = page.get_images(full=True)
                
                for img_idx, img in enumerate(image_list):
                    xref = img[0]  # 图片的交叉引用号
                    
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # 使用OCR识别图片中的文本
                        image_text = self._extract_text_from_image(image_bytes)
                        
                        if image_text.strip():
                            parsed_content.append({
                                "type": "image",
                                "content": image_text,
                                "page": page_num,
                                "image_index": img_idx + 1
                            })
                    except Exception as img_err:
                        logger.warning(f"Error extracting image {img_idx} on page {page_num}: {str(img_err)}")
                
                # 3. 添加文本内容（可能需要排除表格区域）
                text_content = page_data["text"]
                
                # 添加文本内容
                parsed_content.append({
                    "type": "text",
                    "content": text_content,
                    "page": page_num
                })
            
            doc.close()
        except Exception as e:
            logger.error(f"Error in full PDF parsing: {str(e)}")
            # 如果解析失败，回退到基本文本解析
            for page_data in page_map:
                parsed_content.append({
                    "type": "text",
                    "content": page_data["text"],
                    "page": page_data["page"]
                })
        
        return parsed_content

    def _parse_markdown_full(self, text: str, file_path: str, page_map: list) -> list:
        """
        全面解析Markdown文档，提取文本、表格和图片引用

        参数:
            text (str): Markdown文本内容
            file_path (str): Markdown文件路径
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含文本、表格和图片内容的字典列表
        """
        parsed_content = []
        
        try:
            # 将Markdown转换为HTML
            html = markdown.markdown(text, extensions=['tables'])
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. 提取表格
            tables = soup.find_all('table')
            for table_idx, table in enumerate(tables):
                # 确定表格在哪一页
                table_text = table.get_text()
                table_page = 1
                for page_data in page_map:
                    if table_text in page_data["text"]:
                        table_page = page_data["page"]
                        break
                
                # 转换HTML表格为Markdown表格
                md_table = self._html_table_to_markdown(table)
                
                parsed_content.append({
                    "type": "table",
                    "content": md_table,
                    "page": table_page,
                    "table_index": table_idx + 1
                })
            
            # 2. 提取图片引用
            # 获取Markdown文件所在目录
            dir_path = os.path.dirname(file_path)
            
            # 查找图片标签
            img_tags = soup.find_all('img')
            for img_idx, img in enumerate(img_tags):
                img_src = img.get('src', '')
                
                # 确定图片在哪一页
                img_alt = img.get('alt', '')
                img_page = 1
                for page_data in page_map:
                    if img_alt in page_data["text"] or img_src in page_data["text"]:
                        img_page = page_data["page"]
                        break
                
                # 处理相对路径
                if img_src and not img_src.startswith(('http://', 'https://')):
                    img_path = os.path.join(dir_path, img_src)
                    if os.path.exists(img_path):
                        try:
                            # 使用OCR识别图片中的文本
                            image_text = self._extract_text_from_image_file(img_path)
                            
                            if image_text.strip():
                                parsed_content.append({
                                    "type": "image",
                                    "content": image_text,
                                    "page": img_page,
                                    "image_index": img_idx + 1,
                                    "image_alt": img_alt,
                                    "image_src": img_src
                                })
                        except Exception as img_err:
                            logger.warning(f"Error processing image {img_src}: {str(img_err)}")
            
            # 3. 添加文本内容
            # 使用 unstructured 库解析 Markdown 文本
            elements = partition_md(filename=file_path)
            
            for elem_idx, elem in enumerate(elements):
                elem_type = elem.category
                
                # 跳过表格和图片元素，因为已经单独处理了
                if elem_type in ['Table', 'Image']:
                    continue
                
                # 确定元素在哪一页
                elem_text = str(elem)
                elem_page = 1
                for page_data in page_map:
                    if elem_text in page_data["text"]:
                        elem_page = page_data["page"]
                        break
                
                if elem_text.strip():
                    parsed_content.append({
                        "type": elem_type.lower(),
                        "content": elem_text,
                        "page": elem_page
                    })
            
        except Exception as e:
            logger.error(f"Error in full Markdown parsing: {str(e)}")
            # 如果解析失败，回退到基本文本解析
            for page_data in page_map:
                parsed_content.append({
                    "type": "text",
                    "content": page_data["text"],
                    "page": page_data["page"]
                })
        
        return parsed_content

    def _extract_text_from_image(self, image_bytes: bytes) -> str:
        """
        从图片字节数据中提取文本

        参数:
            image_bytes (bytes): 图片的字节数据

        返回:
            str: 从图片中提取的文本
        """
        try:
            # 将字节数据转换为PIL图像
            image = Image.open(io.BytesIO(image_bytes))
            
            # 使用pytesseract进行OCR
            text = pytesseract.image_to_string(image)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            return ""

    def _extract_text_from_image_file(self, image_path: str) -> str:
        """
        从图片文件中提取文本

        参数:
            image_path (str): 图片文件路径

        返回:
            str: 从图片中提取的文本
        """
        try:
            # 使用pytesseract进行OCR
            text = pytesseract.image_to_string(Image.open(image_path))
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image file: {str(e)}")
            return ""

    def _convert_to_markdown_table(self, rows: list) -> str:
        """
        将行数据转换为Markdown表格格式

        参数:
            rows (list): 表格行数据列表

        返回:
            str: Markdown格式的表格
        """
        if not rows:
            return ""
        
        # 创建表头
        header = "| " + " | ".join(rows[0]) + " |"
        separator = "| " + " | ".join(["---" for _ in range(len(rows[0]))]) + " |"
        
        # 创建表格内容
        content = []
        for row in rows[1:]:
            content.append("| " + " | ".join(row) + " |")
        
        # 组合成完整的Markdown表格
        return "\n".join([header, separator] + content)

    def _html_table_to_markdown(self, table) -> str:
        """
        将HTML表格转换为Markdown表格

        参数:
            table: BeautifulSoup表格对象

        返回:
            str: Markdown格式的表格
        """
        rows = []
        
        # 处理表头
        thead = table.find('thead')
        if thead:
            header_row = []
            for th in thead.find_all('th'):
                header_row.append(th.get_text().strip())
            rows.append(header_row)
        else:
            # 如果没有表头，使用第一行作为表头
            first_row = []
            tr = table.find('tr')
            if tr:
                for td in tr.find_all(['td', 'th']):
                    first_row.append(td.get_text().strip())
                rows.append(first_row)
        
        # 处理表格主体
        tbody = table.find('tbody')
        if tbody:
            for tr in tbody.find_all('tr'):
                row = []
                for td in tr.find_all('td'):
                    row.append(td.get_text().strip())
                if row:  # 只添加非空行
                    rows.append(row)
        else:
            # 如果没有tbody标签，直接处理所有tr（跳过第一行，因为已经作为表头）
            for tr in list(table.find_all('tr'))[1:]:
                row = []
                for td in tr.find_all('td'):
                    row.append(td.get_text().strip())
                if row:  # 只添加非空行
                    rows.append(row)
        
        return self._convert_to_markdown_table(rows) 
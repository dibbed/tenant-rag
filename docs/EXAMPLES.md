# Usage Examples

This document provides practical examples of how to use the RAG Telegram Assistant effectively.

## Basic Usage Examples

### Example 1: Adding and Querying Text Content

**Step 1: Add text content**
```
User: /add Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data. It includes supervised learning, unsupervised learning, and reinforcement learning approaches.

Bot: ✅ متن با موفقیت اضافه شد. (1 chunk ایجاد شد)
```

**Step 2: Ask questions**
```
User: /ask What is machine learning?

Bot: 🤖 بر اساس اسناد موجود:

Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data. It includes three main approaches: supervised learning, unsupervised learning, and reinforcement learning.

📚 منابع: text_document_1
```

### Example 2: Working with PDF Documents

**Step 1: Upload PDF**
```
User: /add
[Attach: research_paper.pdf]

Bot: ✅ فایل PDF پردازش و اضافه شد. (15 chunks ایجاد شد)
⏱️ زمان پردازش: 3.2 ثانیه
📄 حجم: 2.1 MB
```

**Step 2: Query the PDF content**
```
User: /ask What are the main findings of this research?

Bot: 🤖 بر اساس اسناد موجود:

The main findings of this research include:

1. The proposed algorithm achieved 94.2% accuracy on the test dataset
2. Processing time was reduced by 35% compared to existing methods
3. The model shows good generalization across different domains
4. Memory usage was optimized by 28%

📚 منابع: research_paper.pdf (صفحات 12, 18, 23)
```

### Example 3: Processing Web Content

**Step 1: Add URL**
```
User: /add https://en.wikipedia.org/wiki/Artificial_intelligence

Bot: ✅ سند از URL دریافت و اضافه شد. (42 chunks ایجاد شد)
⏱️ زمان پردازش: 8.7 ثانیه
🌐 منبع: Wikipedia - Artificial Intelligence
```

**Step 2: Ask about the content**
```
User: /ask When was artificial intelligence first developed?

Bot: 🤖 بر اساس اسناد موجود:

Artificial intelligence was first developed as an academic discipline in 1956 at the Dartmouth Conference. However, the foundational work began earlier with Alan Turing's 1950 paper "Computing Machinery and Intelligence" which proposed the famous Turing Test.

📚 منابع: https://en.wikipedia.org/wiki/Artificial_intelligence
```

## Advanced Usage Examples

### Example 4: Multi-Document Analysis

**Step 1: Add multiple related documents**
```
User: /add https://arxiv.org/pdf/2103.00020.pdf
Bot: ✅ سند از URL دریافت و اضافه شد. (28 chunks ایجاد شد)

User: /add https://arxiv.org/pdf/2106.09685.pdf  
Bot: ✅ سند از URL دریافت و اضافه شد. (31 chunks ایجاد شد)

User: /add Recent advances in transformer architectures have shown remarkable improvements in natural language processing tasks...
Bot: ✅ متن با موفقیت اضافه شد. (3 chunks ایجاد شد)
```

**Step 2: Ask comparative questions**
```
User: /ask Compare the performance of different transformer models mentioned in the documents

Bot: 🤖 بر اساس اسناد موجود:

Based on the documents, here's a comparison of transformer model performance:

**BERT**: 
- GLUE score: 80.5
- Best for: Understanding tasks

**GPT-3**: 
- Few-shot performance: 89.2% on SuperGLUE
- Best for: Generation tasks

**T5**: 
- Text-to-text unified approach
- GLUE score: 88.9
- Best for: Multi-task scenarios

The documents show that model choice depends on the specific task requirements.

📚 منابع: 2103.00020.pdf (صفحه 7), 2106.09685.pdf (صفحه 12), text_document_3
```

### Example 5: Persian Language Usage

**Step 1: Add Persian content**
```
User: /add هوش مصنوعی شاخه‌ای از علوم کامپیوتر است که به ایجاد سیستم‌هایی می‌پردازد که قادر به انجام کارهایی هستند که معمولاً نیاز به هوش انسانی دارند. این شامل یادگیری، استدلال، درک زبان طبیعی و تشخیص الگو می‌شود.

Bot: ✅ متن با موفقیت اضافه شد. (1 chunk ایجاد شد)
```

**Step 2: Ask in Persian**
```
User: /ask هوش مصنوعی چیست؟

Bot: 🤖 بر اساس اسناد موجود:

هوش مصنوعی شاخه‌ای از علوم کامپیوتر است که به ایجاد سیستم‌هایی می‌پردازد که قادر به انجام کارهایی هستند که معمولاً نیاز به هوش انسانی دارند. این حوزه شامل موارد زیر می‌شود:

- یادگیری (Learning)
- استدلال (Reasoning)  
- درک زبان طبیعی (Natural Language Understanding)
- تشخیص الگو (Pattern Recognition)

📚 منابع: text_document_1
```

### Example 6: Technical Documentation

**Step 1: Add API documentation**
```
User: /add
[Attach: api_documentation.pdf]

Bot: ✅ فایل PDF پردازش و اضافه شد. (67 chunks ایجاد شد)
```

**Step 2: Ask specific technical questions**
```
User: /ask How do I authenticate with the API?

Bot: 🤖 بر اساس اسناد موجود:

To authenticate with the API, you need to:

1. **Get API Key**: Register at the developer portal to obtain your API key
2. **Add Header**: Include the key in your request headers:
   ```
   Authorization: Bearer YOUR_API_KEY
   ```
3. **Base URL**: All requests should be made to `https://api.example.com/v1/`
4. **Rate Limits**: Maximum 1000 requests per hour per API key

**Example Request**:
```bash
curl -H "Authorization: Bearer your_key_here" \
     https://api.example.com/v1/users
```

📚 منابع: api_documentation.pdf (صفحه 5)
```

## Workflow Examples

### Example 7: Research Workflow

**Scenario**: Researching a topic across multiple sources

```
# Step 1: Add foundational content
User: /add https://en.wikipedia.org/wiki/Deep_learning
Bot: ✅ سند از URL دریافت و اضافه شد. (38 chunks ایجاد شد)

# Step 2: Add academic papers
User: /add https://arxiv.org/pdf/1706.03762.pdf  # Attention Is All You Need
Bot: ✅ سند از URL دریافت و اضافه شد. (24 chunks ایجاد شد)

# Step 3: Add recent developments
User: /add Recent developments in large language models have shown that scaling up model size and training data leads to emergent capabilities...
Bot: ✅ متن با موفقیت اضافه شد. (2 chunks ایجاد شد)

# Step 4: Comprehensive analysis
User: /ask Provide a comprehensive overview of deep learning evolution from basic concepts to recent LLM developments

Bot: 🤖 بر اساس اسناد موجود:

**Deep Learning Evolution Overview:**

**Foundation (2010s)**:
Deep learning emerged as a subset of machine learning using neural networks with multiple layers. Key breakthroughs included CNNs for image recognition and RNNs for sequence processing.

**Transformer Revolution (2017)**:
The "Attention Is All You Need" paper introduced the Transformer architecture, revolutionizing NLP with:
- Self-attention mechanisms
- Parallel processing capabilities
- Better long-range dependency modeling

**Large Language Models Era (2020s)**:
Recent developments show that scaling up model size and training data leads to emergent capabilities:
- Few-shot learning without fine-tuning
- Complex reasoning abilities
- Multi-modal understanding

This evolution represents a shift from task-specific models to general-purpose AI systems.

📚 منابع: Deep_learning (Wikipedia), 1706.03762.pdf (صفحات 1, 8), text_document_1
```

### Example 8: Document Management Workflow

```
# Check current status
User: /status
Bot: 📊 وضعیت سیستم:
✅ ربات: فعال
✅ OpenAI API: متصل
✅ Vector Store: آماده
📄 اسناد ذخیره شده: 0
🧩 Chunks: 0

# Add documents progressively
User: /add Company policy document: All employees must follow security protocols...
Bot: ✅ متن با موفقیت اضافه شد. (1 chunk ایجاد شد)

User: /add
[Attach: employee_handbook.pdf]
Bot: ✅ فایل PDF پردازش و اضافه شد. (45 chunks ایجاد شد)

# Check updated status
User: /status
Bot: 📊 وضعیت سیستم:
✅ ربات: فعال
✅ OpenAI API: متصل
✅ Vector Store: آماده
📄 اسناد ذخیره شده: 2
🧩 Chunks: 46
⏱️ آخرین بروزرسانی: 2 دقیقه پیش

# Query the knowledge base
User: /ask What are the security protocols mentioned in company documents?

Bot: 🤖 بر اساس اسناد موجود:

According to the company documents, the security protocols include:

1. **Access Control**: All employees must use strong passwords and enable 2FA
2. **Data Handling**: Sensitive data must be encrypted and stored securely
3. **Device Security**: Company devices must have updated antivirus software
4. **Network Security**: Use of VPN required for remote access
5. **Incident Reporting**: Security incidents must be reported within 24 hours

📚 منابع: text_document_1, employee_handbook.pdf (صفحات 12, 15, 18)

# Reset when needed
User: /reset
Bot: ✅ تمام اسناد ذخیره شده پاک شدند.
```

## Error Handling Examples

### Example 9: Handling Common Errors

**Large file error**:
```
User: /add
[Attach: very_large_file.pdf - 75MB]

Bot: ❌ حجم فایل بیش از حد مجاز است. حداکثر حجم مجاز: 50MB
لطفاً فایل کوچک‌تری ارسال کنید یا آن را به چند بخش تقسیم کنید.
```

**Invalid URL error**:
```
User: /add https://invalid-url-that-does-not-exist.com

Bot: ❌ خطا در دریافت محتوا از URL
لطفاً آدرس را بررسی کنید و مجدداً تلاش کنید.
```

**No relevant content error**:
```
User: /ask What is the weather like today?

Bot: ❌ اطلاعات مرتبطی در اسناد ذخیره شده یافت نشد.
لطفاً ابتدا اسناد مرتبط با سوال خود را اضافه کنید.
```

## Best Practices Examples

### Example 10: Optimizing for Better Results

**Good practice - Specific questions**:
```
❌ Bad: /ask Tell me about this document
✅ Good: /ask What are the main benefits of the proposed algorithm mentioned in the research paper?
```

**Good practice - Context-rich documents**:
```
❌ Bad: /add ML is good
✅ Good: /add Machine learning algorithms, particularly supervised learning methods like random forests and support vector machines, have shown significant improvements in classification tasks across various domains including healthcare, finance, and natural language processing.
```

**Good practice - Structured queries**:
```
✅ Good: /ask Compare the accuracy metrics of different models mentioned in the paper
✅ Good: /ask What are the limitations of the proposed approach?
✅ Good: /ask How does this method differ from previous work?
```

### Example 11: Multi-language Best Practices

**Consistent language usage**:
```
# Persian documents with Persian questions
User: /add [Persian PDF document]
User: /ask این روش چه مزایایی دارد؟ ✅

# English documents with English questions  
User: /add [English PDF document]
User: /ask What are the advantages of this method? ✅

# Mixed usage (works but less optimal)
User: /add [English PDF document]
User: /ask این روش چه مزایایی دارد؟ ⚠️
```

## Integration Examples

### Example 12: Using with Development Workflow

```bash
# Add project documentation
User: /add
[Attach: project_requirements.pdf]

User: /add
[Attach: technical_specification.pdf]

User: /add https://github.com/project/wiki/Architecture

# Query during development
User: /ask What are the authentication requirements for the user management module?

User: /ask How should error handling be implemented according to the technical specification?

User: /ask What are the performance requirements mentioned in the project documentation?
```

This comprehensive set of examples should help users understand how to effectively use the RAG Telegram Assistant in various scenarios.

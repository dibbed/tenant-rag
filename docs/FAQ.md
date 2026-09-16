# Frequently Asked Questions (FAQ)

## General Questions

### What is the RAG Telegram Assistant?
The RAG Telegram Assistant is a production-ready Telegram bot that uses Retrieval-Augmented Generation (RAG) to provide accurate, context-aware answers based on documents you upload. It supports PDFs, DOCX, URLs, and plain text in both Persian and English.

### What does RAG mean?
RAG stands for Retrieval-Augmented Generation. It's an AI technique that combines:
1. **Retrieval**: Finding relevant information from your documents
2. **Augmentation**: Adding that information to the AI's context
3. **Generation**: Creating accurate answers based on your specific documents

### What file types are supported?
Currently supported formats:
- **PDF/DOCX files** (up to 50MB)
- **Plain text** (pasted directly)
- **URLs** (web pages, online PDFs)
- **Text files** (.txt)

### What languages are supported?
- **Persian (فارسی)**: Full native support
- **English**: Full native support
- **Auto-detection**: The bot automatically detects your language and responds accordingly

## Setup and Installation

### How do I get a Telegram Bot Token?
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to name your bot
4. Copy the token provided (format: `123456789:ABCdefGHI123jklMNOp`)
5. Add it to your `.env` file as `BOT_TOKEN=your_token_here`

### How do I get an OpenAI API Key?
1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign up or log in to your account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. Add it to your `.env` file as `OPENAI_API_KEY=your_key_here`

### Do I need to pay for OpenAI?
Yes, OpenAI charges for API usage. Costs are typically:
- **Embeddings**: ~$0.0001 per 1K tokens
- **GPT responses**: ~$0.002 per 1K tokens
- Most users spend $1-5 per month for moderate usage

### Can I run this without Docker?
Yes! You can run it directly with Python:
```bash
pip install -r requirements.txt
python main.py
```

However, Docker is recommended for production deployments.

## Usage Questions

### How do I add documents?
Three ways to add documents:
1. **Text**: `/add Your text content here`
2. **File**: Send `/add` then attach a PDF file
3. **URL**: `/add https://example.com/document.pdf`

### Why isn't my PDF being processed?
Common issues:
- **File too large**: Max size is 50MB
- **Corrupted PDF**: Try opening it in a PDF reader first
- **Scanned PDF**: Text-based PDFs work best (not scanned images)
- **Password protected**: Remove password protection first

### How accurate are the answers?
Accuracy depends on:
- **Quality of your documents**: Better documents = better answers
- **Relevance**: Questions should relate to your uploaded content
- **Language consistency**: Best results when question and documents are in the same language

### Can I delete specific documents?
Currently, you can only reset all documents with `/reset`. Individual document deletion is planned for future versions.

### How many documents can I store?
There's no hard limit, but consider:
- **Memory usage**: More documents = more memory needed
- **Response time**: Too many documents may slow responses
- **Cost**: More documents = more OpenAI API usage

## Technical Questions

### What embedding model is used?
By default: `text-embedding-ada-002` from OpenAI
- High quality embeddings
- Supports multiple languages
- Cost-effective

You can change this in your `.env` file:
```env
EMBED_MODEL=text-embedding-3-large  # Higher quality, more expensive
```

### What vector database is used?
**FAISS** (Facebook AI Similarity Search) by default:
- Fast similarity search
- Runs locally (no external dependencies)
- Efficient memory usage

### How is my data stored?
- **Documents**: Stored locally in `data/vector_store/`
- **Embeddings**: Cached locally to reduce API costs
- **No cloud storage**: Everything stays on your server
- **Privacy**: Your documents never leave your infrastructure

### Can I use a different LLM?
Currently optimized for OpenAI models, but the architecture supports:
- Different OpenAI models (GPT-3.5, GPT-4)
- Future support planned for local models (Ollama, etc.)

## Performance and Optimization

### Why are responses slow?
Several factors affect speed:
1. **First-time processing**: Initial document processing takes time
2. **Large documents**: More content = longer processing
3. **API latency**: OpenAI API response times
4. **No caching**: Enable caching for faster repeated queries

### How can I speed up responses?
1. **Enable caching**:
   ```env
   CACHE_TTL=3600  # Cache for 1 hour
   ```

2. **Reduce chunk size**:
   ```env
   CHUNK_SIZE=256  # Smaller chunks, faster processing
   ```

3. **Limit retrieval**:
   ```env
   TOP_K=3  # Retrieve fewer chunks
   ```

### How much memory does it use?
Typical usage:
- **Base system**: ~100-200MB
- **Per document**: ~1-5MB depending on size
- **Large deployments**: Can scale to several GB

## Security and Privacy

### Is my data secure?
Yes:
- **Local storage**: Documents stored on your server only
- **No data sharing**: Nothing sent to third parties except OpenAI for processing
- **User allowlist**: Control who can access your bot
- **No logging**: Sensitive data is not logged

### How do I restrict access?
Add user IDs to your `.env` file:
```env
ALLOW_USERS=123456789,987654321
```

To find your Telegram user ID:
1. Message [@userinfobot](https://t.me/userinfobot)
2. Copy the ID number
3. Add it to the allowlist

### Can others see my documents?
No:
- Each bot instance is private
- Only allowlisted users can interact
- Documents are stored locally on your server
- No shared storage between different bot instances

## Troubleshooting

### Bot doesn't respond to commands
1. **Check bot token**: Verify it's correct in `.env`
2. **Check bot status**: Message [@BotFather](https://t.me/botfather) with `/mybots`
3. **Check logs**: Look at `logs/ragbot.log` for errors
4. **Restart bot**: Stop and start the bot again

### "Unauthorized" error
- **Wrong token**: Double-check your bot token
- **Revoked token**: Generate a new token from [@BotFather](https://t.me/botfather)
- **Formatting**: Ensure no extra spaces in `.env` file

### OpenAI API errors
1. **Invalid key**: Verify your API key is correct
2. **No credits**: Check your OpenAI account balance
3. **Rate limits**: Wait a few minutes and try again
4. **Model access**: Ensure you have access to the specified model

### High memory usage
1. **Reset documents**: Use `/reset` to clear stored data
2. **Reduce chunk size**: Lower `CHUNK_SIZE` in `.env`
3. **Restart regularly**: Restart the bot periodically
4. **Monitor usage**: Use `docker stats` to monitor resource usage

### Slow performance
1. **Enable caching**: Set `CACHE_TTL=3600`
2. **Optimize settings**: Reduce `TOP_K` and `CHUNK_SIZE`
3. **Check network**: Ensure good internet connection
4. **Server resources**: Ensure adequate CPU/memory

## Advanced Usage

### Can I customize the prompts?
Yes, prompts are in `ragbot/rag/qa/prompting.py`. You can modify:
- System prompts
- Language-specific templates
- Response formatting

### Can I add new document types?
Yes, implement a new loader in `ragbot/rag/loaders/`:
```python
from ragbot.rag.loaders.base import BaseLoader

class MyCustomLoader(BaseLoader):
    async def load(self, source: str) -> Document:
        # Your implementation
        pass
```

### Can I use Redis for caching?
Yes, install Redis and configure:
```env
REDIS_URL=redis://localhost:6379
```

### Can I deploy on cloud platforms?
Yes, the bot works on:
- **AWS**: EC2, ECS, Lambda
- **Google Cloud**: Compute Engine, Cloud Run
- **Azure**: Container Instances, App Service
- **DigitalOcean**: Droplets, App Platform
- **Heroku**: With some configuration

## Getting Help

### Where can I get support?
1. **Check this FAQ** first
2. **Review logs**: Look at `logs/ragbot.log`
3. **GitHub Issues**: Search existing issues
4. **Create new issue**: Include logs and configuration (without secrets)

### How do I report bugs?
When reporting bugs, include:
1. **Error message**: Full error from logs
2. **Steps to reproduce**: What you did before the error
3. **Environment**: OS, Python version, Docker version
4. **Configuration**: Your `.env` settings (without secrets)

### How do I request features?
1. **Check existing issues**: Feature might already be requested
2. **Create feature request**: Describe the use case
3. **Consider contributing**: Pull requests welcome!

## Contributing

### How can I contribute?
1. **Report bugs**: Help identify issues
2. **Suggest features**: Share your ideas
3. **Write code**: Submit pull requests
4. **Improve docs**: Help make documentation better
5. **Share examples**: Show how you use the bot

### Development setup
```bash
git clone https://github.com/your-repo/rag-telegram-assistant.git
cd rag-telegram-assistant
pip install -e ".[dev]"
pytest  # Run tests
```

## Roadmap

### Planned features
- Individual document deletion
- Web interface
- More document types (DOCX, images)
- Local LLM support (Ollama)
- Multi-user support
- Document versioning
- Advanced search filters

### How can I stay updated?
- **Watch the repository** on GitHub
- **Follow releases** for new versions
- **Join discussions** in GitHub Discussions

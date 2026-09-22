# Plugin Examples

This directory contains example plugins that demonstrate the RAG Bot Plugin Architecture capabilities.

## Available Examples

### 1. Simple Plugin (`simple_plugin.py`)

A basic example plugin that demonstrates:

- Query enhancement and preprocessing
- Response formatting
- Basic hook system usage
- Configuration management

**Features:**

- Enhances queries with contextual phrases
- Custom response formatting with prefixes
- Confidence score improvements

### 2. Logging Analytics Plugin (`logging_plugin.py`)

A comprehensive analytics plugin that provides:

- User interaction tracking
- Query performance monitoring
- System usage analytics
- Comprehensive reporting

**Features:**

- Real-time performance metrics
- User behavior analysis
- Query pattern recognition
- Data retention management

### 3. Security Plugin (`security_plugin.py`)

An advanced security plugin offering:

- Content filtering and moderation
- Threat detection and analysis
- Anomaly detection
- Security monitoring and reporting

**Features:**

- Suspicious query detection
- Document content analysis
- User behavior monitoring
- Automatic blocking mechanisms

## Plugin Types Supported

- **Query Enhancement** - Modify or improve query processing
- **Analytics** - Track and analyze system usage
- **Security** - Monitor and protect against threats
- **Data Processing** - Transform or process data
- **Integration** - Connect with external systems
- **UI Enhancement** - Improve user interface

## Usage Examples

### Loading via CLI:

```bash
# Load a plugin
python -m ragbot.cli plugin load --path plugins/examples/simple_plugin.py

# Load with configuration
python -m ragbot.cli plugin load --path plugins/examples/security_plugin.py --config '{"sensitivity_level": "high"}'

# List loaded plugins
python -m ragbot.cli plugin list

# Check plugin status
python -m ragbot.cli plugin status --plugin-id simple_plugin
```

### Loading via Telegram Bot:

```
/load_plugin plugins/examples/logging_plugin.py
/list_plugins
/plugin_status logging_analytics_plugin
```

## Plugin Development

To create your own plugin:

1. Inherit from `BasePlugin`
2. Implement required abstract methods:

   - `plugin_name` property
   - `plugin_version` property
   - `plugin_description` property
   - `plugin_type` property
   - `initialize()` method
   - `execute()` method
   - `cleanup()` method

3. Register hooks for integration points
4. Validate your plugin structure
5. Test thoroughly before deployment

## Hook Types Available

- `pre_document_ingest` - Before document processing
- `post_document_ingest` - After document processing
- `pre_query` - Before query execution
- `post_query` - After query execution
- `pre_response` - Before response formatting
- `post_response` - After response completion
- `on_user_interaction` - User interaction events
- `on_error` - Error handling events

## Configuration

Plugins support configuration through:

- Default configuration values
- Runtime configuration updates
- Environment-specific settings
- Dynamic configuration reloading

## Security Considerations

- All plugins are validated for security issues
- Sandboxed execution environment
- Restricted import capabilities
- Content filtering and validation
- Access control and permissions

## Performance Impact

- Minimal performance overhead
- Async/await compatibility
- Resource management
- Memory optimization
- Parallel execution support

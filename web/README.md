# 贵客来 Web

贵客来贵州好物智能购物 Agent 的 React + TypeScript 前端。

## Overview

This UI provides a responsive interface for the Guikelai Guizhou shopping agent, with streaming chat, image search, a grounded local catalog, cart and budget tools.

## Architecture

### Components Structure

```
src/
├── components/
│   ├── chat/                    # Chat window, messages, parsing, input
│   ├── cart/                    # Cart panel
│   ├── me/                      # Profile and favorites
│   ├── orders/                  # Purchase history
│   ├── Navbar.tsx               # Navigation header
│   └── Footer.tsx               # Footer component
├── config/
│   └── appConfig.ts             # Centralized configuration
├── types/
│   ├── chat.ts                  # Chat and product types
│   ├── cart.ts                  # Cart types
│   └── orders.ts                # Order and history types
├── lib/                         # Identity, images, favorites, sharing
├── api/                         # Cart, orders, and history clients
└── styles/                      # Global and chat styles
```

### Key Features

- **Type Safety**: Full TypeScript implementation with proper type definitions
- **Configuration Management**: Centralized config for easy customization
- **Error Handling**: Comprehensive error handling with user feedback
- **Image Upload**: Secure image upload with validation
- **Real-time Streaming**: Live message streaming from the backend
- **Responsive Design**: Mobile-friendly interface
- **Accessibility**: ARIA labels and semantic HTML

## Development

### Prerequisites

- Node.js 16+
- npm or yarn

### Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start development server:
   ```bash
   npm start
   ```

3. Build for production:
   ```bash
   npm run build
   ```

### Available Scripts

- `npm start` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues
- `npm run format` - Format code with Prettier

## Configuration

The application uses a centralized configuration system in `src/config/appConfig.ts`. Key configuration options:

- **API Settings**: Backend URLs and endpoints
- **UI Settings**: Default images, categories, and styling
- **Feature Flags**: Enable/disable features such as safety checks and image upload
- **File Upload**: Size limits and allowed file types

## Type Definitions

Domain types are defined in `src/types/chat.ts`, `src/types/cart.ts`, and `src/types/orders.ts`:

- `MessageData` - Chat message structure
- `ApiRequest/ApiResponse` - API communication types
- `FileUploadResult` - Image upload handling
- `ErrorState` - Error handling types

## Utility Functions

Shared helpers are split by responsibility under `src/lib/`:

- File conversion (base64 ↔ blob)
- User session management
- API request helpers
- File validation
- Download utilities

## Styling

The application uses:
- **Tailwind CSS** for utility-first styling
- **Material-UI** for component library
- **Emotion** for styled components
- **Custom CSS** for chat-specific styling

## Security

- **XSS Protection**: DOMPurify for HTML sanitization
- **File Validation**: Strict file type and size validation
- **Input Sanitization**: All user inputs are properly sanitized

## Performance

- **Code Splitting**: Lazy loading of components
- **Memoization**: React.memo for expensive components
- **Efficient Rendering**: Optimized re-renders with proper keys
- **Streaming**: Real-time message streaming without blocking

## Testing

The application includes:
- Unit tests for utility functions
- Component testing with React Testing Library
- Integration tests for API communication
- E2E tests for critical user flows

## Deployment

The application can be deployed using:
- Docker containers
- Static hosting (Netlify, Vercel)
- Traditional web servers

## Contributing

1. Follow TypeScript best practices
2. Use proper error handling
3. Add tests for new features
4. Update documentation
5. Follow the existing code style

## Troubleshooting

### Common Issues

1. **TypeScript Errors**: Ensure all dependencies are properly typed
2. **Build Failures**: Check for missing dependencies
3. **API Connection**: Verify backend is running and accessible
4. **Image Upload**: Check file size and type restrictions

### Debug Mode

Enable debug logging by setting `NODE_ENV=development` in your environment.

## License

Apache 2.0 License - see LICENSE file for details.

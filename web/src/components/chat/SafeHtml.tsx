/**
 * Safe HTML rendering component with DOMPurify sanitization
 */

import React from 'react';
import DOMPurify from 'dompurify';
import { SafeHTMLProps } from '../../types/chat';

const SafeHTML: React.FC<SafeHTMLProps> = ({ html }) => {
  // Sanitize the HTML to prevent XSS attacks
  const safeHTML = DOMPurify.sanitize(html);

  return <div dangerouslySetInnerHTML={{ __html: safeHTML }} />;
};

export default SafeHTML;

import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, X, Check, ChevronDown, Package } from 'lucide-react';
import { useChat } from '@/contexts/ChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription, 
  DialogFooter 
} from '@/components/ui/dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Link } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import api from '@/utils/api';
import { Message } from '@/types';
import { useToast } from '@/components/ui/use-toast';

// Backend API endpoints
const BACKEND_CHAT_ENDPOINT = '/webhook/chat';
const CHAT_API_ENDPOINT = '/chat';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const [showSettingsAlert, setShowSettingsAlert] = useState(false);
  const [showProductPopover, setShowProductPopover] = useState(false);
  const [showProductTypePopover, setShowProductTypePopover] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [selectedProductType, setSelectedProductType] = useState('');
  const [customProduct, setCustomProduct] = useState('');
  const [customProductType, setCustomProductType] = useState('');
  const [availableProducts, setAvailableProducts] = useState<string[]>([]);
  const [availableProductTypes, setAvailableProductTypes] = useState<string[]>([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(false);
  const { toast } = useToast();
  const { 
    sendMessage, 
    isLoading, 
    getCurrentSession, 
    dateRange, 
    setChatState,
    editingMessageId,
    setEditingMessageId,
    editMessage,
    messagesWithErrors,
    setMessagesWithErrors,
    sessions
  } = useChat();
  const { user, isAuthenticated } = useAuth();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const isSettingsComplete = user?.fbGraphApiKey && user?.fbAdAccountId;
  const currentSession = getCurrentSession();
  const isFirstPrompt = !currentSession || (currentSession && currentSession.messages.length === 0);
  const showQuestionnaireInChat = isFirstPrompt && currentSession?.messages.length === 0;
  const isEditing = !!editingMessageId;

  // Debug logging
  useEffect(() => {
    console.log('ChatInput Debug:', {
      currentSession: currentSession?.id,
      messagesLength: currentSession?.messages.length,
      isFirstPrompt,
      isEditing,
      shouldShowProductSelection: isFirstPrompt && !isEditing
    });
  }, [currentSession, isFirstPrompt, isEditing]);

  // If we're in editing mode, populate the input with the message content
  useEffect(() => {
    if (editingMessageId && currentSession) {
      const messageToEdit = currentSession.messages.find(m => m.id === editingMessageId);
      if (messageToEdit) {
        setMessage(messageToEdit.content);
        if (textareaRef.current) {
          textareaRef.current.focus();
        }
      }
    }
  }, [editingMessageId, currentSession]);

  // Focus on the textarea when the component mounts
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  // Fetch available products and product types
  const fetchProducts = async () => {
    if (isLoadingProducts) return;
    
    setIsLoadingProducts(true);
    try {
      const response = await api.get('/ad-analysis/products');
      setAvailableProducts(response.data.products || []);
      setAvailableProductTypes(response.data.product_types || []);
    } catch (error) {
      console.error('Error fetching products:', error);
      toast({
        title: "Error",
        description: "Failed to load product suggestions",
        variant: "destructive",
      });
    } finally {
      setIsLoadingProducts(false);
    }
  };

  // Load products when component mounts or when starting a new chat
  useEffect(() => {
    fetchProducts();
  }, [currentSession]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!message.trim()) return;

    if (isEditing && editingMessageId) {
      // We're editing a message
      try {
        // Get the current session before any changes
        const currentSession = getCurrentSession();
        if (!currentSession) return;
        
        // Find the message index
        const messageIndex = currentSession.messages.findIndex(m => m.id === editingMessageId);
        if (messageIndex === -1) return;
        
        // Find the next message (which should be the bot response to this message)
        let responseMessageIndex = -1;
        
        // Look for the next bot message after this user message
        for (let i = messageIndex + 1; i < currentSession.messages.length; i++) {
          if (currentSession.messages[i].role === 'bot') {
            responseMessageIndex = i;
            break;
          }
        }
        
        // Determine which messages to keep - we'll keep all messages up to
        // and including the user message being edited, but remove the bot response
        const messagesToKeep = currentSession.messages.slice(0, messageIndex + 1);
        
        // Create a copy of the message with updated content
        const updatedMessage = {
          ...currentSession.messages[messageIndex],
          content: message
        };
        
        // Replace the edited message in our array
        messagesToKeep[messageIndex] = updatedMessage;
        
        // Start loading state
        setChatState(prev => ({
          ...prev,
          isLoading: true,
        }));
        
        // Update in the database - just the edited message and remove response
        try {
          console.log('Updating session in database with edited message');
          const backendSessionId = currentSession._id || currentSession.id;
          await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
            messages: messagesToKeep
          });
          console.log('Session updated in database successfully');
          
          toast({
            title: "Success",
            description: "Message updated, getting new response...",
          });
        } catch (error) {
          console.error('Error updating session in API after editing:', error);
          toast({
            title: "Error",
            description: "Failed to save your edited message",
            variant: "destructive",
          });
          setChatState(prev => ({ ...prev, isLoading: false }));
          return;
        }
        
        // Update the state with edited message (remove bot response)
        setChatState(prev => {
          // Make a deep copy of sessions to avoid reference issues
          const updatedSessions = prev.sessions.map(session => {
            if (session.id === currentSession.id) {
              return {
                ...session,
                messages: messagesToKeep,
                updatedAt: new Date()
              };
            }
            return session;
          });
          
          return {
            ...prev,
            sessions: updatedSessions,
          };
        });
        
        // Clear editing state
        setEditingMessageId(null);
        setMessage('');
          
        // Now resend the message to n8n
        try {
          console.log('Sending edited message to webhook');
          // Send to webhook to get new response
          const response = await api.post(BACKEND_CHAT_ENDPOINT, {
            userMessage: updatedMessage.content,
            previousMessages: messagesToKeep
              .filter(msg => msg.id !== updatedMessage.id)
              .slice(-5)
              .map(msg => ({
                role: msg.role,
                content: msg.content,
              })),
            dateRange: {
              startDate: dateRange.startDate,
              endDate: dateRange.endDate,
            },
          });
          
          console.log('Got response from webhook:', response.data);
          
          // Extract the response content
          const responseContent = extractOutputFromResponse(response.data);
          
          // Create bot message
          const botMessage: Message = {
            id: `msg_${Math.random().toString(36).substring(2, 11)}`,
            content: responseContent,
            role: 'bot',
            timestamp: new Date(),
          };
          
          // Add the response to our messages array
          const messagesWithResponse = [...messagesToKeep, botMessage];
          
          // Update state with the new response
          setChatState(prev => {
            // Deep copy again to avoid reference issues
            const updatedSessions = prev.sessions.map(session => {
              if (session.id === currentSession.id) {
                return {
                  ...session,
                  messages: messagesWithResponse,
                  updatedAt: new Date()
                };
              }
              return session;
            });
            
            return {
              ...prev,
              sessions: updatedSessions,
              isLoading: false,
            };
          });
          
          // Clear any error flags
          if (messagesWithErrors.includes(updatedMessage.id)) {
            setMessagesWithErrors(prev => prev.filter(id => id !== updatedMessage.id));
          }
          
          // Save the updated session with new bot response to the API
          try {
            console.log('Saving new response to database');
            const backendSessionId = currentSession._id || currentSession.id;
            await api.put(`${CHAT_API_ENDPOINT}/sessions/${backendSessionId}`, {
              messages: messagesWithResponse
            });
            console.log('New response saved to database successfully');
            
            toast({
              title: "Success",
              description: "Message updated and new response received",
            });
          } catch (error) {
            console.error('Error updating session in API after getting response:', error);
            toast({
              title: "Warning",
              description: "Response received but couldn't be saved to database",
              variant: "destructive",
            });
          }
        } catch (error) {
          console.error('Error getting response from webhook:', error);
          setChatState(prev => ({
            ...prev,
            isLoading: false,
            error: error instanceof Error ? error.message : 'Failed to get response',
          }));
          
          // Mark the message as having an error
          setMessagesWithErrors(prev => [...prev, updatedMessage.id]);
          
          toast({
            title: "Error",
            description: "Failed to get a response. You can try again.",
            variant: "destructive",
          });
        }
      } catch (error) {
        console.error('Error updating and resending message:', error);
        setChatState(prev => ({
          ...prev,
          isLoading: false,
        }));
        
        toast({
          title: "Error",
          description: "Failed to update and resend message",
          variant: "destructive",
        });
      }
      return;
    }
    
    if (!isSettingsComplete) {
      setShowSettingsAlert(true);
      return;
    }
    
    // Prepare product information if selected
    const productInfo = {
      product: selectedProduct || customProduct || '',
      product_type: selectedProductType || customProductType || ''
    };
    
    // Check for date range on first message, but don't append it to the message
    if (isFirstPrompt) {
      if (!dateRange.startDate || !dateRange.endDate) {
        alert('Please set date range in the Analysis Settings panel before starting a new chat.');
        return;
      }
      
      // Send the message with product info if provided
      const hasProductInfo = productInfo.product || productInfo.product_type;
      await sendMessage(message, hasProductInfo ? productInfo : undefined);
    } else {
      // Regular message - include product info if provided
      const hasProductInfo = productInfo.product || productInfo.product_type;
      await sendMessage(message, hasProductInfo ? productInfo : undefined);
    }
    
    setMessage('');
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setMessage('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    } else if (e.key === 'Escape' && isEditing) {
      handleCancelEdit();
    }
  };
  
  // Extract output from webhook response
  const extractOutputFromResponse = (response: any): string => {
    // Check for different response formats
    if (typeof response === 'string') {
      return response;
    }
    
    if (response && response.output) {
      return response.output;
    }
    
    if (response && response.result) {
      return response.result;
    }
    
    if (response && response.message) {
      return response.message;
    }
    
    // Fallback
    return JSON.stringify(response);
  };
  
  return (
    <>
      <form onSubmit={handleSubmit} className="relative">
        {isEditing && (
          <div className="bg-yellow-50 p-2 mb-2 rounded text-sm flex justify-between items-center">
            <span>Editing message</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleCancelEdit}
              className="h-6 p-1"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        
        {/* Product Selection - show for all messages */}
        {!isEditing && (
          <div className="mb-3 space-y-2">
            <div className="text-xs text-muted-foreground mb-2">
              Product Information (Optional)
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Product Name Selection */}
              <div>
                <Popover open={showProductPopover} onOpenChange={setShowProductPopover}>
                  <PopoverTrigger asChild>
                    <Button 
                      variant="outline" 
                      className="w-full justify-between text-left h-9"
                      type="button"
                    >
                      <div className="flex items-center gap-2">
                        <Package className="h-4 w-4" />
                        <span className="truncate">
                          {(selectedProduct || customProduct) || 'Select Product'}
                        </span>
                      </div>
                      <ChevronDown className="h-4 w-4 flex-shrink-0" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-80" align="start">
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <h4 className="font-medium">Product Name</h4>
                        <p className="text-sm text-muted-foreground">
                          Select from your existing products or enter a custom one.
                        </p>
                      </div>
                      
                      <div className="space-y-3">
                        <div>
                          {isLoadingProducts ? (
                            <div className="text-sm text-muted-foreground">Loading products...</div>
                          ) : availableProducts.length > 0 ? (
                            <div className="space-y-1 max-h-40 overflow-y-auto">
                              <div className="text-xs text-muted-foreground mb-1">From your ads:</div>
                              {availableProducts.map((product) => (
                                <Button
                                  key={product}
                                  variant={selectedProduct === product ? "default" : "ghost"}
                                  size="sm"
                                  className="w-full justify-start text-left h-8"
                                  type="button"
                                  onClick={() => {
                                    setSelectedProduct(product);
                                    setCustomProduct('');
                                  }}
                                >
                                  <span className="truncate">{product}</span>
                                </Button>
                              ))}
                            </div>
                          ) : (
                            <div className="text-sm text-muted-foreground">No products found in your ads</div>
                          )}
                          
                          <Input
                            placeholder="Or enter custom product name"
                            value={customProduct}
                            onChange={(e) => {
                              setCustomProduct(e.target.value);
                              if (e.target.value) setSelectedProduct('');
                            }}
                          />
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          type="button"
                          onClick={() => {
                            setSelectedProduct('');
                            setCustomProduct('');
                          }}
                        >
                          Clear
                        </Button>
                        <Button
                          size="sm"
                          type="button"
                          onClick={() => setShowProductPopover(false)}
                        >
                          Done
                        </Button>
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </div>

              {/* Product Type Selection */}
              <div>
                <Popover open={showProductTypePopover} onOpenChange={setShowProductTypePopover}>
                  <PopoverTrigger asChild>
                    <Button 
                      variant="outline" 
                      className="w-full justify-between text-left h-9"
                      type="button"
                    >
                      <div className="flex items-center gap-2">
                        <Package className="h-4 w-4" />
                        <span className="truncate">
                          {(selectedProductType || customProductType) || 'Select Type'}
                        </span>
                      </div>
                      <ChevronDown className="h-4 w-4 flex-shrink-0" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-80" align="start">
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <h4 className="font-medium">Product Type</h4>
                        <p className="text-sm text-muted-foreground">
                          Select from existing types or enter a custom category.
                        </p>
                      </div>
                      
                      <div className="space-y-3">
                        <div>
                          {availableProductTypes.length > 0 ? (
                            <div className="space-y-1 max-h-40 overflow-y-auto">
                              <div className="text-xs text-muted-foreground mb-1">From your ads:</div>
                              {availableProductTypes.map((type) => (
                                <Button
                                  key={type}
                                  variant={selectedProductType === type ? "default" : "ghost"}
                                  size="sm"
                                  className="w-full justify-start text-left h-8"
                                  type="button"
                                  onClick={() => {
                                    setSelectedProductType(type);
                                    setCustomProductType('');
                                  }}
                                >
                                  <span className="truncate">{type}</span>
                                </Button>
                              ))}
                            </div>
                          ) : (
                            <div className="text-sm text-muted-foreground">No product types found in your ads</div>
                          )}
                          
                          <Input
                            placeholder="Or enter custom product type"
                            value={customProductType}
                            onChange={(e) => {
                              setCustomProductType(e.target.value);
                              if (e.target.value) setSelectedProductType('');
                            }}
                          />
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          type="button"
                          onClick={() => {
                            setSelectedProductType('');
                            setCustomProductType('');
                          }}
                        >
                          Clear
                        </Button>
                        <Button
                          size="sm"
                          type="button"
                          onClick={() => setShowProductTypePopover(false)}
                        >
                          Done
                        </Button>
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </div>
            </div>
          </div>
        )}
        
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isEditing ? "Edit your message..." : "Type your message..."}
          rows={2}
          className="w-full pr-20 resize-none"
          disabled={isLoading && !isEditing}
        />
        <div className="absolute bottom-2 right-2 flex gap-1">
          {isEditing && (
            <Button 
              type="button" 
              size="icon" 
              onClick={handleCancelEdit}
              className="h-9 w-9"
            >
              <X className="h-5 w-5" />
            </Button>
          )}
          <Button 
            type="submit" 
            size="icon" 
            className="h-9 w-9"
            disabled={(isLoading && !isEditing) || !message.trim()}
          >
            {isLoading && !isEditing ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-t-transparent" />
            ) : isEditing ? (
              <Check className="h-5 w-5" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>
      </form>
      
      {/* Settings Alert Dialog */}
      <Dialog open={showSettingsAlert} onOpenChange={setShowSettingsAlert}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-yellow-500" />
              Setup Required
            </DialogTitle>
            <DialogDescription>
              You need to set up your Facebook API credentials before you can chat with AdScribe AI.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              AdScribe AI needs access to your Facebook Ads data through the Facebook Graph API. Please go to settings to add your credentials.
            </p>
          </div>
          <DialogFooter>
            <Link to="/settings" className="w-full">
              <Button className="w-full">Go to Settings</Button>
            </Link>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ChatInput;
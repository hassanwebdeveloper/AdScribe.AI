from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import logging
from ..Nodes import TextClassifierNode, AdScriptGeneratorNode, GeneralResponseNode

# Set up logging
logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    """State that flows through the agent graph"""
    user_message: str
    previous_messages: List[Dict[str, str]]
    ad_analyses: List[Dict[str, Any]]
    product_info: Optional[Dict[str, str]]
    classification: Optional[str]
    final_response: Optional[str]
    error: Optional[str]

class AdScriptGeneratorAgent:
    """
    LangGraph AI Agent for ad script generation with dynamic classification
    """
    
    def __init__(self, classification_classes: Optional[Dict[str, str]] = None):
        """
        Initialize the Ad Script Generator Agent with dynamic classification classes.
        
        Args:
            classification_classes: Dictionary mapping class names to descriptions.
                                  If None, fetches from database or uses fallback defaults.
        """
        # Initialize classification classes
        self.classification_classes = None
        
        # Initialize node instances with temporary classes, will be updated in _initialize_classification_classes
        temp_classes = {
            "ad_script": "If user wants to write new ad speech or video script or text but not code.",
            "default": "it is default category all remaining query should lie under this category"
        }
        
        self.text_classifier = TextClassifierNode(temp_classes)
        self.ad_script_generator = AdScriptGeneratorNode()
        self.general_response_generator = GeneralResponseNode()
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Initialize classification classes (will update the graph if needed)
        if classification_classes is not None:
            self.classification_classes = classification_classes
            self._update_classifier()
        # Note: For async initialization from database, call initialize_from_database() separately
    
    async def initialize_from_database(self):
        """
        Initialize classification classes from database.
        This should be called after creating the agent instance.
        """
        try:
            from app.services.classification_classes_service import ClassificationClassesService
            
            # Fetch ad_script_generator classification classes from database
            db_classes = await ClassificationClassesService.get_classification_classes_by_name("ad_script_generator")
            
            if db_classes and db_classes.classes:
                logger.info("Loaded classification classes from database")
                self.classification_classes = db_classes.classes
                self._update_classifier()
            else:
                logger.warning("No ad_script_generator classification classes found in database, using hardcoded fallback")
                # Keep the temporary classes as fallback
                self.classification_classes = {
                    "ad_script": "If user wants to write new ad speech or video script or text but not code.",
                    "default": "it is default category all remaining query should lie under this category"
                }
                
        except Exception as e:
            logger.error(f"Error loading classification classes from database: {e}")
            # Use fallback classes
            self.classification_classes = {
                "ad_script": "If user wants to write new ad speech or video script or text but not code.",
                "default": "it is default category all remaining query should lie under this category"
            }
    
    def _update_classifier(self):
        """Update the text classifier with new classification classes"""
        if self.classification_classes:
            self.text_classifier = TextClassifierNode(self.classification_classes)
            # Rebuild the graph with updated classifier
            self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the agent workflow graph"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classify_text", self.text_classifier.classify_text)
        workflow.add_node("generate_ad_script", self.ad_script_generator.generate_ad_script)
        workflow.add_node("generate_general_response", self.general_response_generator.generate_general_response)
        
        # Add edges
        workflow.set_entry_point("classify_text")
        
        # Conditional routing based on classification
        workflow.add_conditional_edges(
            "classify_text",
            self._route_based_classification,
            {
                "ad_script": "generate_ad_script",
                "default": "generate_general_response"
            }
        )
        
        # Both nodes end the workflow
        workflow.add_edge("generate_ad_script", END)
        workflow.add_edge("generate_general_response", END)
        
        return workflow.compile()
    
    def _route_based_classification(self, state: AgentState) -> str:
        """
        Route to appropriate node based on classification and ad analyses availability
        """
        classification = state.get("classification", "default")
        ad_analyses = state.get("ad_analyses", [])
        
        # For ad script generation, we need both the right classification AND ad analyses data
        if classification == "ad_script" and ad_analyses and len(ad_analyses) > 0:
            logger.info("Routing to ad script generation")
            return "ad_script"
        else:
            logger.info(f"Routing to general response (classification: {classification}, ad_analyses: {len(ad_analyses) if ad_analyses else 0})")
            return "default"
    
    async def process_request(
        self, 
        user_message: str, 
        previous_messages: List[Dict[str, str]] = None,
        ad_analyses: List[Dict[str, Any]] = None,
        product_info: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Process a user request through the LangGraph workflow
        
        Args:
            user_message: The user's message/query
            previous_messages: List of previous conversation messages
            ad_analyses: List of ad analysis data (if available)
            product_info: Dictionary containing product information
            
        Returns:
            Dict containing the response and any additional data
        """
        try:
            # Initialize state
            initial_state: AgentState = {
                "user_message": user_message,
                "previous_messages": previous_messages or [],
                "ad_analyses": ad_analyses or [],
                "product_info": product_info,
                "classification": None,
                "final_response": None,
                "error": None
            }
            
            # Run the workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            # Prepare response
            response = {
                "output": final_state.get("final_response", "No response generated"),
                "success": final_state.get("error") is None,
                "classification": final_state.get("classification", "default"),
                "error": final_state.get("error", "")
            }
            
            logger.info(f"Ad Script Generator Agent workflow completed. Classification: {response['classification']}, Success: {response['success']}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in Ad Script Generator Agent workflow: {str(e)}")
            return {
                "output": f"Sorry, I encountered an error while processing your request: {str(e)}",
                "success": False,
                "classification": "default",
                "error": str(e)
            }
    
    def update_classification_classes(self, new_classes: Dict[str, str]):
        """
        Update the classification classes dynamically.
        
        Args:
            new_classes: New dictionary of class names to descriptions
        """
        self.classification_classes = new_classes
        self._update_classifier()
        logger.info(f"Updated classification classes: {list(new_classes.keys())}")

# Create instance with default classes
ad_script_generator_agent = AdScriptGeneratorAgent()
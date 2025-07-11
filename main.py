# main.py
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import dashboard pages
from pages.user_360_dashboard_new import render_user_360_dashboard
from pages.roles_360_dashboard import render_roles_360_dashboard
# Add other dashboard imports here as you create them, e.g.:
# from pages.warehouse_360_dashboard import render_warehouse_360_dashboard

def main():
    """
    Main function to run the Streamlit application.
    Sets up page configuration, sidebar navigation, and renders selected pages.
    """
    st.set_page_config(
        page_title="Snowflake Analytics Dashboard",
        page_icon="❄️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.title("❄️ Snowflake Analytics")
    st.sidebar.markdown("---") # Visual separator

    # Navigation options
    pages = {
        "User 360 Dashboard": render_user_360_dashboard,
        "Roles 360 Dashboard": render_roles_360_dashboard,
        # Add other dashboard names and their rendering functions here:
        # "Warehouse 360 Dashboard": render_warehouse_360_dashboard,
    }

    # Use a selectbox for navigation
    selected_page = st.sidebar.selectbox(
        "Navigate Dashboards",
        list(pages.keys()),
        key="main_navigation_selectbox",
        help="Select a dashboard to view specific Snowflake insights."
    )
    st.sidebar.markdown("---")

    # Display app version or info in sidebar
    st.sidebar.info("Version 1.0.0 | Developed for Snowflake Analytics")


    # Render the selected page
    try:
        if selected_page in pages:
            pages[selected_page]() # Call the rendering function for the selected page
        else:
            st.error("Dashboard not found. Please select a valid option from the sidebar.")
            logger.error(f"Attempted to navigate to unknown page: {selected_page}")
    except Exception as e:
        logger.exception(f"An unhandled error occurred while rendering page '{selected_page}'.")
        st.error(
            f"Oops! An unexpected error occurred while loading this dashboard. "
            f"Please try again or contact support if the issue persists. "
            f"Error details: {e}"
        )

    # Optional: Footer or global info
    st.markdown(
        """
        <style>
            footer {visibility: hidden;} /* Hide default Streamlit footer */
            .reportview-container .main footer {
                visibility: visible;
                display: flex;
                justify-content: flex-end;
                align-items: center;
                padding: 10px;
                position: fixed;
                bottom: 0;
                width: 100%;
                background-color: #f0f2f6; /* Streamlit's default background */
                border-top: 1px solid #e0e0e0;
                font-size: 0.8rem;
                color: #888;
            }
        </style>
        <div class="footer">
            Powered by Streamlit and Snowflake. Data from ACCOUNT_USAGE views.
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
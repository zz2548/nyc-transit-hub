# NYC Transit Hub

A real-time web application providing updates, schedules, and transit information for New York City's public transportation system.

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Technologies](#technologies)
- [Environment Setup](#environment-setup)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Environment Variables](#environment-variables)
  - [Database Setup](#database-setup)
  - [API Keys](#api-keys)
- [Development Workflow](#development-workflow)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Project Overview

NYC Transit Hub provides real-time transit information including subway and bus schedules, service alerts, and station accessibility information. This application integrates with the MTA API to deliver up-to-date information to commuters in NYC.

## Features

- Interactive transit map with route visualization
- Real-time service status dashboard
- User accounts with favorites and personalized alerts
- Trip planning functionality
- Elevator and escalator accessibility information
- Multilingual support
- Mobile-responsive design

## Technologies

### Frontend
-TBD

### Backend
- Python with Flask
- SQLite with SQLAlchemy
- Firebase Authentication

### DevOps
- Git and GitHub for version control
- Vercel for deployment

## Environment Setup

### Prerequisites

Before setting up the project, ensure you have the following installed:

- [Node.js](https://nodejs.org/) (v16.0.0 or higher)
- [npm](https://www.npmjs.com/) (v8.0.0 or higher) or [Yarn](https://yarnpkg.com/) (v1.22.0 or higher)
- [Python](https://www.python.org/) (v3.9.0 or higher)
- [pip](https://pip.pypa.io/en/stable/installation/) (latest version)
- [Git](https://git-scm.com/downloads)

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/nyc-transit-hub.git
   cd nyc-transit-hub
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install backend dependencies:
   ```bash
   cd backend
   pip install .
   
   # For development dependencies
   pip install ".[dev]"
   ```

4. Install protocol buffers for GTFS Realtime:
   ```bash
   pip install protobuf
   pip install gtfs-realtime-bindings
   ```

5. Initialize the database:
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. Start the Flask development server:
   ```bash
   flask run
   ```
   The server should now be running at http://localhost:5000/

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```

2. Install frontend dependencies:
   ```bash
   # Using npm
   npm install

   # Using Yarn
   yarn install
   ```

3. Start the React development server:
   ```bash
   # Using npm
   npm start

   # Using Yarn
   yarn start
   ```
   The frontend should now be running at http://localhost:3000/

### Environment Variables

1. Create a `.env` file in the backend directory with the following variables:
   ```
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your_secret_key_here
   MTA_API_KEY=your_mta_api_key_here
   FIREBASE_CONFIG=path_to_firebase_credentials.json
   ```

2. Create a `.env` file in the frontend directory with the following variables:
   ```
   REACT_APP_API_URL=http://localhost:5000/api
   REACT_APP_FIREBASE_API_KEY=your_firebase_api_key
   REACT_APP_FIREBASE_AUTH_DOMAIN=your_firebase_auth_domain
   REACT_APP_FIREBASE_PROJECT_ID=your_firebase_project_id
   REACT_APP_FIREBASE_STORAGE_BUCKET=your_firebase_storage_bucket
   REACT_APP_FIREBASE_MESSAGING_SENDER_ID=your_firebase_messaging_sender_id
   REACT_APP_FIREBASE_APP_ID=your_firebase_app_id
   ```

### Database Setup

The application uses SQLite for development. The database file will be created automatically when you initialize the database as described in the backend setup section.

For production, you may want to use a more robust database like PostgreSQL. Configuration for different environments is located in `backend/config.py`.

### API Keys

1. **MTA API Key**:
   - Register for an API key at [MTA Developer Portal](https://api.mta.info/)
   - Add your key to the backend `.env` file

2. **Firebase Project Setup**:
   - Create a new Firebase project at [Firebase Console](https://console.firebase.google.com/)
   - Set up Authentication with Email/Password provider
   - Download your Firebase Admin SDK service account key (JSON) and save it securely
   - Add the path to this file in your backend `.env` file
   - Add the web app Firebase configuration to your frontend `.env` file

## Development Workflow

1. **Creating a new feature**:
   ```bash
   git checkout -b feature/your-feature-name
   # Make your changes
   git add .
   git commit -m "Add your feature description"
   git push origin feature/your-feature-name
   ```

2. **Running tests**:
   ```bash
   # Backend tests
   cd backend
   pytest

   # Frontend tests
   cd frontend
   npm test
   ```

3. **Code linting**:
   ```bash
   # Backend
   cd backend
   flake8

   # Frontend
   cd frontend
   npm run lint
   ```

## Project Structure

```
nyc-transit-hub/
├── README.md
├── backend/
│   ├── app.py              # Flask application entry point
│   ├── config.py           # Application configuration
│   ├── requirements.txt    # Python dependencies
│   ├── migrations/         # Database migrations
│   ├── services/
│   │   ├── mta_service.py  # MTA API integration
│   │   └── auth_service.py # Authentication service
│   ├── models/             # Database models
│   └── routes/             # API routes
├── frontend/
│   ├── package.json        # JavaScript dependencies
│   ├── public/             # Static files
│   └── src/
│       ├── components/     # React components
│       ├── pages/          # Page components
│       ├── store/          # Redux store
│       ├── services/       # API services
│       ├── utils/          # Utility functions
│       ├── i18n/           # Translations
│       ├── App.js          # Main app component
│       └── index.js        # Entry point
└── docs/                   # Documentation
```

## Testing

### Backend Testing

We use pytest for backend testing:

```bash
cd backend
pytest
```

### Frontend Testing

We use Jest and React Testing Library for frontend tests:

```bash
cd frontend
npm test
```

## Deployment

### Deploying to Vercel

1. Install the Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Deploy the frontend:
   ```bash
   cd frontend
   vercel
   ```

3. Deploy the backend as serverless functions:
   ```bash
   cd backend
   vercel
   ```

4. Link the frontend and backend in production by updating the API URL in the frontend environment variables.

## Troubleshooting

### Common Issues

1. **MTA API Connection Issues**:
   - Check your API key is valid and not expired
   - Ensure you're making requests to the correct endpoints
   - Check MTA API status for any outages

2. **Firebase Authentication Issues**:
   - Verify Firebase configuration is correct
   - Ensure Authentication providers are enabled in Firebase Console
   - Check if the service account key has the right permissions

3. **Database Migration Errors**:
   - Try removing the migrations folder and recreate the migrations
   ```bash
   rm -rf migrations
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

### Getting Help

If you encounter any issues not covered in this documentation, please:

1. Check the existing GitHub issues
2. Create a new issue with detailed information about the problem
3. Reach out to the project maintainers

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

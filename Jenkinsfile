pipeline {
    agent any
    
    options {
        timeout(time: 10, unit: 'MINUTES')
        timestamps()
    }
    
    stages {
        stage('Checkout Info') {
            steps {
                echo "Build #${env.BUILD_NUMBER}"
                echo "Commit: ${env.GIT_COMMIT}"
                sh 'ls -la'
            }
        }
        
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install -r requirements.txt
                '''
            }
        }
        
        stage('Lint') {
            steps {
                sh '''
                    . venv/bin/activate
                    ruff check .
                '''
            }
        }
        
        stage('Unit Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    python -m pytest -v --cov=src --cov-fail-under=80
                '''
            }
        }
    }
    
    post {
        success { echo '✅ Pipeline passed!' }
        failure { echo '❌ Pipeline failed.' }
    }
}
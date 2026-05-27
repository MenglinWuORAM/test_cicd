pipeline {
    agent any
    
    options {
        timeout(time: 10, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
    }
    
    environment {
        IMAGE_NAME = 'test-cicd'
        IMAGE_TAG  = "${env.BUILD_NUMBER}"
    }
    
    stages {
        stage('Checkout Info') {
            steps {
                echo "=========================================="
                echo "Build #${env.BUILD_NUMBER}"
                echo "Commit: ${env.GIT_COMMIT}"
                echo "Branch: ${env.GIT_BRANCH}"
                echo "=========================================="
                sh 'ls -la'
            }
        }
        
        stage('Build Image') {
            steps {
                script {
                    docker.build("${IMAGE_NAME}:${IMAGE_TAG}", ".")
                }
            }
        }
        
        stage('Lint') {
            steps {
                script {
                    docker.image("${IMAGE_NAME}:${IMAGE_TAG}").inside {
                        sh 'ruff check .'
                    }
                }
            }
        }
        
        stage('Unit Tests') {
            steps {
                script {
                    docker.image("${IMAGE_NAME}:${IMAGE_TAG}").inside {
                        sh 'python -m pytest -v --cov=src --cov-report=term --cov-fail-under=80'
                    }
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Pipeline passed!'
        }
        failure {
            echo '❌ Pipeline failed.'
        }
        always {
            echo "Cleaning up image ${IMAGE_NAME}:${IMAGE_TAG}"
            sh "docker rmi ${IMAGE_NAME}:${IMAGE_TAG} || true"
        }
    }
}
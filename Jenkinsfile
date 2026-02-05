pipeline{
    agent any
    options {
        // This is required if you want to clean before build
        skipDefaultCheckout(true)
    }
    stages {
        stage('Checkout') {
            steps {
                // Checkout the source code from your version control system (e.g., Git)
                checkout scm
            }
        }
        stage('Deploy') {
            steps {
                script {
                    // Define the paths
                    def workspacePath = "${WORKSPACE}/"
                    // def targetPath = "/root/kfc/"
                    def branch = sh(script: "git name-rev --name-only HEAD", returnStdout: true).trim()
                    branch = branch.replaceAll(/^remotes\\//, "").replaceAll(/^origin\\//, "")
                    echo "Current branch: ${branch}"

            

                    def targetPath =  (branch == "master") ? "/home/lina/apps/kfc/" : "/root/kfc/"
                    def scriptFile = (branch == "master") ? "prod_start_script.sh" : "dev_start_script.sh"
                    def scriptPath = "${targetPath}${scriptFile}"


                    // Clean the target directory
                    sh "sudo rm -rf ${targetPath}*"

                    // Copy files from the workspace to the target directory
                    sh "sudo cp -r ${workspacePath}* ${targetPath}"


                    sh "sudo chmod +x ${scriptPath}"
                    sh "sudo ${scriptPath}"
                }
            }
        }
    }
    post { 
        failure { 
            echo 'Deployment Failed'
        }
        success { 
            echo 'Deployment Successful'
        }
        unstable { 
            echo 'Deployment Unstable'
        }
    }
}
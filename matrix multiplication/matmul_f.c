#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/shm.h>
#include <unistd.h>

int size, num_processes;
double *matrix1, *matrix2, *matrix3;

#define SHM_KEY1 0x1234
#define SHM_KEY2 0x5678
#define SHM_KEY3 0x9ABC

void init_matrix(double *matrix, int size) {
    for (int i = 0; i < size * size; ++i) {
        matrix[i] = 1.0;
    }
}

void print_matrix(double *matrix, int size) {
    for (int i = 0; i < size; ++i) {
        for (int j = 0; j < size; ++j) {
            printf("%lf ", matrix[i * size + j]);
        }
        printf("\n");
    }
}

void worker(int pid) {
    int portion_size = size / num_processes;
    int row_start = pid * portion_size;
    int row_end = (pid + 1) * portion_size;

    for (int i = row_start; i < row_end; ++i) {
        for (int j = 0; j < size; ++j) {
            double sum = 0;
            for (int k = 0; k < size; ++k) {
                sum += matrix1[i * size + k] * matrix2[k * size + j];
            }
            matrix3[i * size + j] = sum;
        }
    }
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <matrix size> <number of processes>\n", argv[0]);
        return -1;
    }

    size = atoi(argv[1]);
    num_processes = atoi(argv[2]);

    if (size % num_processes != 0) {
        fprintf(stderr, "Matrix size %d must be a multiple of number of processes %d\n", size, num_processes);
        return -1;
    }

    int shm_id1 = shmget(SHM_KEY1, size * size * sizeof(double), IPC_CREAT | 0666);
    int shm_id2 = shmget(SHM_KEY2, size * size * sizeof(double), IPC_CREAT | 0666);
    int shm_id3 = shmget(SHM_KEY3, size * size * sizeof(double), IPC_CREAT | 0666);

    if (shm_id1 < 0 || shm_id2 < 0 || shm_id3 < 0) {
        perror("shmget");
        exit(1);
    }

    matrix1 = shmat(shm_id1, NULL, 0);
    matrix2 = shmat(shm_id2, NULL, 0);
    matrix3 = shmat(shm_id3, NULL, 0);

    if (matrix1 == (double *)-1 || matrix2 == (double *)-1 || matrix3 == (double *)-1) {
        perror("shmat");
        exit(1);
    }

    init_matrix(matrix1, size);
    init_matrix(matrix2, size);

    if (size <= 10) {
        printf("Matrix 1:\n");
        print_matrix(matrix1, size);
        printf("Matrix 2:\n");
        print_matrix(matrix2, size);
    }

    struct timeval tstart, tend;
    gettimeofday(&tstart, NULL);

    pid_t pid;
    for (int i = 0; i < num_processes; ++i) {
        pid = fork();
        if (pid == 0) {
            // Child process
            worker(i);
            shmdt(matrix1);
            shmdt(matrix2);
            shmdt(matrix3);
            exit(0);
        } else if (pid < 0) {
            perror("Fork failed");
            exit(1);
        }
    }

    // Wait for all child processes to complete
    for (int i = 0; i < num_processes; ++i) {
        wait(NULL);
    }

    gettimeofday(&tend, NULL);

    if (size <= 10) {
        printf("Matrix 3:\n");
        print_matrix(matrix3, size);
    }

    double exectime = (tend.tv_sec - tstart.tv_sec) * 1000.0; // sec to ms
    exectime += (tend.tv_usec - tstart.tv_usec) / 1000.0; // us to ms

    printf("Number of processes: %d\tExecution time: %.3lf sec\n",
           num_processes, exectime / 1000.0);

    // Detach and remove shared memory
    shmdt(matrix1);
    shmdt(matrix2);
    shmdt(matrix3);
    shmctl(shm_id1, IPC_RMID, NULL);
    shmctl(shm_id2, IPC_RMID, NULL);
    shmctl(shm_id3, IPC_RMID, NULL);

    return 0;
}

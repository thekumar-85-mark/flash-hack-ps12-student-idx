#include <ctype.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_FRAGS 100

typedef struct Node {
    int val;
    struct Node *left;
    struct Node *right;
} Node;

typedef struct {
    int vals[3];
    bool has_val[3];
} Fragment;

typedef struct {
    Fragment frags[MAX_FRAGS];
    int num_frags;
    Node *nodes_by_root[MAX_FRAGS];
    int root_ids[MAX_FRAGS];
    int used_roots[MAX_FRAGS];
} RecoveryCtx;

static Node *new_node(int val) {
    Node *n = (Node *)malloc(sizeof(Node));
    if (!n) {
        fprintf(stderr, "Memory allocation failed.\n");
        exit(EXIT_FAILURE);
    }
    n->val = val;
    n->left = NULL;
    n->right = NULL;
    return n;
}

static int find_root_index(RecoveryCtx *ctx, int val) {
    for (int i = 0; i < ctx->num_frags; i++) {
        if (ctx->root_ids[i] == val) return i;
    }
    return -1;
}

static bool appears_as_child(RecoveryCtx *ctx, int target) {
    for (int i = 0; i < ctx->num_frags; i++) {
        Fragment *f = &ctx->frags[i];
        if (f->has_val[1] && f->vals[1] == target) return true;
        if (f->has_val[2] && f->vals[2] == target) return true;
    }
    return false;
}

static bool build_fragments(RecoveryCtx *ctx, const char **err) {
    for (int i = 0; i < ctx->num_frags; i++) {
        Fragment *f = &ctx->frags[i];
        if (!f->has_val[0]) {
            *err = "Fragment missing root ID.";
            return false;
        }
        int r = f->vals[0];
        if (find_root_index(ctx, r) != -1) {
            *err = "Duplicate fragment root ID.";
            return false;
        }
        if (f->has_val[1] && f->vals[1] >= r) {
            *err = "Local BST violation: left child >= root.";
            return false;
        }
        if (f->has_val[2] && f->vals[2] <= r) {
            *err = "Local BST violation: right child <= root.";
            return false;
        }

        ctx->root_ids[i] = r;
        ctx->used_roots[i] = 0;

        Node *n = new_node(r);
        if (f->has_val[1]) n->left = new_node(f->vals[1]);
        if (f->has_val[2]) n->right = new_node(f->vals[2]);
        ctx->nodes_by_root[i] = n;
    }
    return true;
}

static Node *stitch(RecoveryCtx *ctx, Node *node) {
    if (node == NULL) return NULL;

    if (node->left == NULL && node->right == NULL) {
        int idx = find_root_index(ctx, node->val);
        if (idx != -1 && !ctx->used_roots[idx]) {
            ctx->used_roots[idx] = 1;
            Node *frag_node = ctx->nodes_by_root[idx];
            free(node);
            node = frag_node;
        }
    }

    node->left = stitch(ctx, node->left);
    node->right = stitch(ctx, node->right);
    return node;
}

static bool is_valid_bst(Node *node, long long low, long long high, const char **err) {
    if (node == NULL) return true;
    if (!((long long)node->val > low && (long long)node->val < high)) {
        *err = "Global BST ordering violation in merged tree.";
        return false;
    }
    if (!is_valid_bst(node->left, low, (long long)node->val, err)) return false;
    return is_valid_bst(node->right, (long long)node->val, high, err);
}

static void print_inorder(Node *node, bool *first) {
    if (node == NULL) return;
    print_inorder(node->left, first);
    if (!(*first)) printf(", ");
    printf("%d", node->val);
    *first = false;
    print_inorder(node->right, first);
}

static void print_tree(Node *node, int depth, const char *side) {
    if (node == NULL) return;
    for (int i = 0; i < depth; i++) printf("  ");
    printf("[%s] %d\n", side, node->val);
    print_tree(node->left, depth + 1, "L");
    print_tree(node->right, depth + 1, "R");
}

static void free_tree(Node *node) {
    if (node == NULL) return;
    free_tree(node->left);
    free_tree(node->right);
    free(node);
}

static void free_unmerged_fragments(RecoveryCtx *ctx, int root_idx) {
    for (int i = 0; i < ctx->num_frags; i++) {
        if (i != root_idx && !ctx->used_roots[i] && ctx->nodes_by_root[i]) {
            free_tree(ctx->nodes_by_root[i]);
        }
    }
}

static void recover(RecoveryCtx *ctx) {
    const char *err = NULL;
    if (ctx->num_frags <= 0) {
        printf("IMPOSSIBLE: No fragments provided.\n");
        return;
    }
    if (!build_fragments(ctx, &err)) {
        printf("IMPOSSIBLE: %s\n", err);
        free_unmerged_fragments(ctx, -1);
        return;
    }

    int root_idx = -1;
    int root_candidates = 0;
    for (int i = 0; i < ctx->num_frags; i++) {
        if (!appears_as_child(ctx, ctx->root_ids[i])) {
            root_idx = i;
            root_candidates++;
        }
    }

    if (root_candidates == 0) {
        printf("IMPOSSIBLE: No global root found (possible cycle).\n");
        free_unmerged_fragments(ctx, -1);
        return;
    }
    if (root_candidates > 1) {
        printf("IMPOSSIBLE: Multiple disconnected root candidates found.\n");
        free_unmerged_fragments(ctx, -1);
        return;
    }

    ctx->used_roots[root_idx] = 1;
    Node *merged_root = stitch(ctx, ctx->nodes_by_root[root_idx]);

    for (int i = 0; i < ctx->num_frags; i++) {
        if (!ctx->used_roots[i]) {
            printf("IMPOSSIBLE: Unused/unreachable fragment with root %d.\n", ctx->root_ids[i]);
            free_tree(merged_root);
            free_unmerged_fragments(ctx, root_idx);
            return;
        }
    }

    if (!is_valid_bst(merged_root, LLONG_MIN, LLONG_MAX, &err)) {
        printf("IMPOSSIBLE: %s\n", err);
        free_tree(merged_root);
        return;
    }

    bool first = true;
    printf("\nSUCCESS\nMerged Root: %d\nInorder Traversal: [", merged_root->val);
    print_inorder(merged_root, &first);
    printf("]\nTree Structure:\n");
    print_tree(merged_root, 0, "Root");

    free_tree(merged_root);
}

static bool parse_token(const char *tok, int *out_val, bool *has_val) {
    if (strcmp(tok, "-") == 0) {
        *has_val = false;
        *out_val = 0;
        return true;
    }
    char *endptr = NULL;
    long val = strtol(tok, &endptr, 10);
    if (endptr == tok || *endptr != '\0' || val < INT_MIN || val > INT_MAX) {
        return false;
    }
    *has_val = true;
    *out_val = (int)val;
    return true;
}

static bool parse_fragment_line(const char *line, Fragment *frag) {
    char buf[256];
    strncpy(buf, line, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char *tokens[4];
    int count = 0;
    char *tok = strtok(buf, " \t\r\n");
    while (tok != NULL) {
        if (count >= 4) return false;
        tokens[count++] = tok;
        tok = strtok(NULL, " \t\r\n");
    }

    if (count < 1 || count > 3) return false;

    for (int i = 0; i < 3; i++) {
        frag->vals[i] = 0;
        frag->has_val[i] = false;
    }

    for (int i = 0; i < count; i++) {
        if (!parse_token(tokens[i], &frag->vals[i], &frag->has_val[i])) {
            return false;
        }
    }

    if (!frag->has_val[0]) return false;
    return true;
}

int main(void) {
    RecoveryCtx ctx;
    memset(&ctx, 0, sizeof(ctx));

    char line[256];
    printf("Enter number of fragments (1-%d): ", MAX_FRAGS);
    fflush(stdout);

    if (!fgets(line, sizeof(line), stdin)) {
        printf("IMPOSSIBLE: Failed to read fragment count.\n");
        return 1;
    }

    int n = 0;
    if (sscanf(line, "%d", &n) != 1 || n < 1 || n > MAX_FRAGS) {
        printf("IMPOSSIBLE: Invalid number of fragments.\n");
        return 1;
    }

    ctx.num_frags = n;
    printf("Enter %d fragments (format: root [left] [right], use '-' for missing child):\n", n);
    fflush(stdout);

    for (int i = 0; i < n; i++) {
        printf("Fragment %d: ", i + 1);
        fflush(stdout);
        if (!fgets(line, sizeof(line), stdin)) {
            printf("IMPOSSIBLE: Unexpected end of input at fragment %d.\n", i + 1);
            return 1;
        }
        if (!parse_fragment_line(line, &ctx.frags[i])) {
            printf("IMPOSSIBLE: Invalid format on fragment %d.\n", i + 1);
            return 1;
        }
    }

    recover(&ctx);
    return 0;
}

// SPDX-License-Identifier: AGPL-3.0-or-later

#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>

extern int NSExtensionMain(int argc, const char *argv[]);

@interface ActionRequestHandler : NSViewController <NSExtensionRequestHandling>
@property(nonatomic, assign) BOOL requestStarted;
@end

@implementation ActionRequestHandler

- (void)beginRequestWithExtensionContext:(NSExtensionContext *)context {
    if (!self.requestStarted) {
        self.requestStarted = YES;
        [self processExtensionContext:context];
    }
}

- (void)loadView {
    self.view = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 1, 1)];
}

- (void)processExtensionContext:(NSExtensionContext *)context {
    dispatch_group_t group = dispatch_group_create();
    NSMutableArray<NSURL *> *pdfURLs = [NSMutableArray array];

    for (NSExtensionItem *item in context.inputItems) {
        for (NSItemProvider *provider in item.attachments) {
            if (![provider hasItemConformingToTypeIdentifier:@"com.adobe.pdf"]) {
                continue;
            }
            dispatch_group_enter(group);
            [provider loadInPlaceFileRepresentationForTypeIdentifier:@"com.adobe.pdf"
                                                    completionHandler:^(NSURL *value,
                                                                        BOOL isInPlace,
                                                                        NSError *error) {
                if (value != nil && error == nil) {
                    @synchronized (pdfURLs) {
                        [pdfURLs addObject:value];
                    }
                }
                dispatch_group_leave(group);
            }];
        }
    }

    dispatch_group_notify(group, dispatch_get_main_queue(), ^{
        if (pdfURLs.count == 0) {
            NSError *error = [NSError errorWithDomain:NSCocoaErrorDomain
                                                  code:NSFileReadUnsupportedSchemeError
                                              userInfo:@{
                NSLocalizedDescriptionKey: @"No local PDF files were selected."
            }];
            [context cancelRequestWithError:error];
            return;
        }

        NSMutableArray<NSURLQueryItem *> *queryItems = [NSMutableArray array];
        for (NSURL *url in pdfURLs) {
            NSError *bookmarkError = nil;
            NSData *bookmark = [url bookmarkDataWithOptions:0
                            includingResourceValuesForKeys:nil
                                             relativeToURL:nil
                                                     error:&bookmarkError];
            if (bookmark == nil || bookmarkError != nil) {
                continue;
            }
            [queryItems addObject:[NSURLQueryItem queryItemWithName:@"bookmark"
                                                               value:[bookmark base64EncodedStringWithOptions:0]]];
        }
        if (queryItems.count == 0) {
            NSError *error = [NSError errorWithDomain:NSCocoaErrorDomain
                                                  code:NSFileReadNoPermissionError
                                              userInfo:@{
                NSLocalizedDescriptionKey: @"Could not authorize the selected PDF files."
            }];
            [context cancelRequestWithError:error];
            return;
        }
        NSURLComponents *components = [[NSURLComponents alloc] init];
        components.scheme = @"fspdfcompressor";
        components.host = @"compress";
        components.queryItems = queryItems;
        if (![NSWorkspace.sharedWorkspace openURL:components.URL]) {
            NSError *error = [NSError errorWithDomain:NSCocoaErrorDomain
                                                  code:NSFileNoSuchFileError
                                              userInfo:@{
                NSLocalizedDescriptionKey: @"Could not open FS PDF Compressor."
            }];
            [context cancelRequestWithError:error];
            return;
        }
        // This is an in-place action. Returning the original extension items tells
        // Finder to keep the selected files while the host app compresses them.
        [context completeRequestReturningItems:context.inputItems completionHandler:nil];
    });
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        return NSExtensionMain(argc, argv);
    }
}

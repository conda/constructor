#import "ExtraPage.h"

@implementation ExtraPage

- (NSString *)title
{
    return [[NSBundle bundleForClass:[self class]] localizedStringForKey:@"Extra Page" value:nil table:nil];
}

@end
